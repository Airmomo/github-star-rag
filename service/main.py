import os
import json
import glob
import time
import asyncio
import uvicorn
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from service.chat_start_github import ChatStarGithub
from service.util import github, parse
from chromadb import Collection
from chromadb import PersistentClient as PersistentChroma
from chromadb.utils.embedding_functions.openai_embedding_function import OpenAIEmbeddingFunction
from embeding_functions.zhipu_embeding_function import ZhiPuAIEmbeddingFunction
from openai import OpenAI, BadRequestError
from fastapi.responses import JSONResponse

app = FastAPI()

# 配置 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源。你可以根据需要限制来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有HTTP头
)


class Requirement(BaseModel):
    detail: str = Field(default="Nothing")


class Settings(BaseModel):
    github_token: str = Field(default="")
    llm_api_base: str = Field(default="")
    llm_api_key: str = Field(default="")
    llm_model_name: str = Field(default="")
    embedding_api_base: str = Field(default="")
    embedding_api_key: str = Field(default="")
    embedding_model_name: str = Field(default="")
    re_save: bool = Field(default=False)
    # 文档（原始长文本）目录路径
    directory_path: str = Field(default="static/repo_md")
    # 检索择优限制数量
    retriever_n_results: int = Field(default=10)

    @property
    def github_login_username(self) -> str:
        """Return username of the auth github"""
        return github.get_username(self.github_token)

    @property
    def llm(self) -> OpenAI:
        """Return llm."""
        return OpenAI(api_key=self.llm_api_key, base_url=self.llm_api_base)

    @property
    def chat_client(self) -> ChatStarGithub:
        """Return chat client."""
        return ChatStarGithub(llm=self.llm, model=self.llm_model_name)

    @property
    def chroma_collection(self) -> Collection:
        """Return a chroma collection"""
        # 选择使用的嵌入模型
        if not (self.embedding_api_base and self.embedding_api_key and self.embedding_model_name):
            embedding_function = None
            embedding_function_name = 'chroma_embedding'
        elif "bigmodel" in self.embedding_api_base:
            embedding_function = ZhiPuAIEmbeddingFunction(
                api_key=self.embedding_api_key,
                api_base=self.embedding_api_base,
                model_name=self.embedding_model_name
            )
            embedding_function_name = 'zhipuai_embedding'
        else:
            embedding_function = OpenAI(
                api_key=self.embedding_api_key,
                api_base=self.embedding_api_base,
                model_name=self.embedding_model_name
            )
            embedding_function_name = 'openai_embedding'
        # 使用 Chroma 作为本地持久化的向量数据库
        chroma_client = PersistentChroma(path=f"vector/chat-github-star/{embedding_function_name}")
        collection = chroma_client.create_collection(# name="embeddings", 优化：按照向量集合来隔离不同用户Star的项目信息，去除后续检索时的筛选步骤，提高检索效率。
                                                    name=self.github_login_username,
                                                    get_or_create=True,
                                                    # Chroma默认使用的是all-MiniLM-L6-v2模型来进行 embeddings
                                                    # 这里使用嵌入模型API对文本进行向量计算
                                                    embedding_function=embedding_function)
        return collection


# 获取本地配置初始化全局设置
setting_persistent = Settings()
current_dir = os.path.dirname(os.path.abspath(__file__))
settings_path = os.path.join(current_dir, "settings.json")
if os.path.exists(settings_path):
    with open(settings_path, "r") as f:
        setting_json_str = f.read()
    setting_persistent = setting_persistent.model_validate_json(
        setting_json_str)


@app.post("/save-settings")
async def save_settings(settings: Settings):
    global setting_persistent
    try:
        # 获取当前路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        settings_path = os.path.join(current_dir, "settings.json")
        # 保存设置到 settings.json 文件
        with open(settings_path, "w") as f:
            setting_json_str = settings.model_dump_json()
            f.write(setting_json_str)
        setting_persistent = setting_persistent.model_validate_json(
            setting_json_str)
        return JSONResponse({"message": "Settings saved successfully!", "success": 1})
    except Exception as e:
        print(f"Error occurred: {e}")  # 输出具体的错误信息
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-settings")
async def get_settings():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        settings_path = os.path.join(current_dir, "settings.json")
        if not os.path.exists(settings_path):
            # 如果文件不存在，返回空对象
            return {}
        with open(settings_path, "r") as f:
            setting_json_str = f.read()
        return json.loads(setting_json_str)
    except Exception as e:
        print(f"Error occurred: {e}")  # 输出具体的错误信息
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/init-github-data")
def init_github_readme():
    global setting_persistent
    try:
        print(
            '正在获取用户Github中Star的项目信息...')
        # 获取当前用户Star的仓库信息
        starred_repositories = github.get_starred_repository()
        print(
            '用户Github中Star的项目信息获取完成，进行保存...'
        )
        github.save_repositories_readme_as_markdown(
            starred_repositories, directory=setting_persistent.directory_path, re_save=setting_persistent.re_save
        )
        return JSONResponse({"message": "Github-star-data inited successfully!", "success": 1})
    except Exception as e:
        print(f"Error occurred: {e}")  # 输出具体的错误信息
        raise HTTPException(status_code=500, detail=str(e))


@ app.get("/init-chroma-collection")
def init_chroma_collection():
    global setting_persistent
    try:
        # 数据库存储向量和元数据
        md_files_dict = parse.get_md_files_dict(
            setting_persistent.directory_path)
        for index, (md_file_name, md_content) in enumerate(md_files_dict.items(), start=1):
            print(
                f"({index}/{len(md_files_dict.keys())}) - 文件正在进行压缩和向量计算，当前文件：{md_file_name}"
            )
            result = setting_persistent.chroma_collection.get(ids=md_file_name,
                                                            # 优化：检索时增加where条件会增加较多的耗时，所以这里在遍历文件时采用模糊匹配即可，后续检索时再增加条件筛选。
                                                            #   where={
                                                            #       "who_starred": {
                                                            #           "$eq": setting_persistent.github_login_username
                                                            #       }
                                                            #   }
                                                            )
            # 不重复计算已存在的向量
            if result['ids']:
                summarize = result["documents"][0]
                is_vaild = parse.repository_summary_vaild(summarize)
                if not is_vaild:
                    while not is_vaild:
                        # 生成的总结不充分，需重新生成
                        print(
                            f"生成的内容不符合要求，需要LLM重新生成总结，当前文件：{md_file_name}"
                        )
                        summarize = setting_persistent.chat_client.get_summarize_retry(
                            md_content, last_sumarize=summarize)
                        is_vaild = parse.repository_summary_vaild(summarize)
                    setting_persistent.chroma_collection.add(documents=summarize, ids=md_file_name, metadatas={
                        "md_file_source_path": md_file_name,
                        "who_starred": setting_persistent.github_login_username
                    })
                else:
                    print(
                        f"({index}/{len(md_files_dict.keys())}) - 文件已向量化，不会重复进行向量计算，当前文件：{md_file_name}"
                    )
            else:
                try:
                    summarize = setting_persistent.chat_client.get_summarize(
                        md_content)
                    while not parse.repository_summary_vaild(summarize):
                        # 生成的总结不充分，需重新生成
                        print(
                            f"生成的内容不符合要求，需要LLM重新生成总结，当前文件：{md_file_name}"
                        )
                        summarize = setting_persistent.chat_client.get_summarize_retry(
                            md_content, last_sumarize=summarize)
                    setting_persistent.chroma_collection.add(documents=summarize, ids=md_file_name, metadatas={
                        "md_file_source_path": md_file_name,
                        "who_starred": setting_persistent.github_login_username
                    })
                    print(
                        f"({index}/{len(md_files_dict.keys())}) - 文件向量计算已完成：{md_file_name} "
                    )
                except BadRequestError as e:
                    print(
                        f"({index}/{len(md_files_dict.keys())}) - 向量计算文件：{md_file_name} 时发生了一个错误：{e.message}"
                    )
        return JSONResponse({"message": "Chroma-collection inited successfully!", "success": 1})
    except Exception as e:
        print(f"Error occurred: {e}")  # 输出具体的错误信息
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search")
def search(requirement: Requirement):
    global setting_persistent
    print(
        f"正在检索与之相关的Repositories：{requirement.detail}"
    )
    try:
        # 检索向量相关的数据，返回n_results个最相关的数据
        retriever_prompt = setting_persistent.chat_client.get_retriever_prompt(
            requirement.detail)
        relative_documnets = setting_persistent.chroma_collection.query(
            query_texts=[
                retriever_prompt
            ],
            n_results=setting_persistent.retriever_n_results,
            # 优化：在初始化时按照向量集合来隔离不同用户Star的项目信息，去除后续检索时的条件查询步骤，提高检索效率。
            # 条件查询，查询元数据中的who_starred字段，确保不会搜索到其他用户star的repository
            # where={
            #     "who_starred": {
            #         "$eq": setting_persistent.github_login_username
            #     }
            # }
        )["documents"][0]
        print(f"检索到与之相关的Repositories：{relative_documnets}")
        print(f"检索完成！等待LLM评估与选择的最终结果......")
        result = {}
        # 将检索到的信息交给 LLM 进行评估和选择
        if relative_documnets and len(relative_documnets) > 1:
            appropriate_repositories = setting_persistent.chat_client.get_appropriate_repositories(
                documents=relative_documnets, requirement=requirement.detail)
            result = parse.repositories_xml2json_out_parse(
                xml_content=parse.xml_message_pre_process(appropriate_repositories))
        print(f"LLM评估与选择的最终结果（可能为空）：{result}")
        return result
    except Exception as e:
        print(f"Error occurred: {e}")  # 输出具体的错误信息
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)

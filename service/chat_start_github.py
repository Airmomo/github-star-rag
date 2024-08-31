"""Airmomo
"""
import os

from typing import List
from dotenv import load_dotenv
from chromadb import PersistentClient as PersistentChroma
from chromadb.utils.embedding_functions.openai_embedding_function import OpenAIEmbeddingFunction
from embeding_functions.zhipu_embeding_function import ZhiPuAIEmbeddingFunction
from openai import OpenAI, BadRequestError
from util import github, parse


class ChatStarGithub():
    """Main Class"""

    def __init__(self, llm: OpenAI, model: str):
        """Init 

        Args:
            llm (OpenAI): LLM客户端实例, 需要使用 OpenAI 接口规范的模型
            model (str): LLM模型的名称
        """
        self.llm = llm
        self.model = model

    def get_summarize(self, document_content: str) -> str:
        """通过LLM对文档内容（原始长文本）进行总结并按XML格式输出的总结内容。

        Args:
            document_content (str): 文档内容

        Returns:
            str: 生成的以文档内容进行总结的Repository描述信息
        """
        chat_completion = self.llm.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system",
                    "content": "你是一个文档总结助手，用中文输出总结的内容，并使用XML格式化返回的内容，生成的内容以示例为准，不需要生成其他标签的内容。示例：\
                        ```xml<Repository> \
                        <name>(该Repository的名称)</name> \
                        <owner>(该Repository的作者)</owner> \
                        <url>(该Repository的Github链接)</url> \
                        <descrpition>(... 结合提供文档信息进行分析，生成一段对于该Repository描述，描述必须包括其实现的功能、适用的应用场景等具有关键性、相关性的内容。 ...)</descrpition> \
                        <keywords>(... 根据提供文档信息生成关于该Repository合适的中文关键字。关键词之间应以逗号隔开。 ...)</keywords> \
                        </Repository>```"},
                {"role": "user",
                    "content": "```markdown(... partial document content ...)```"},
                {"role": "assistant",
                    "content": "```xml<Repository> \
                        <name>(该Repository的名称)</name> \
                        <owner>(该Repository的作者)</owner> \
                        <url>(该Repository的Github链接)</url> \
                        <descrpition>(... 结合提供文档信息进行分析，生成一段对于该Repository描述，描述必须包括其实现的功能、适用的应用场景等具有关键性、相关性的内容。 ...)</descrpition> \
                        <keywords>(... 根据提供文档信息生成关于该Repository合适的中文关键字。关键词之间应以逗号隔开。 ...)</keywords> \
                        </Repository>```"},
                {"role": "user", "content": f"```markdown{document_content}```"}
            ]
        )
        assistant_generate_message = chat_completion.choices[0].message.content
        return assistant_generate_message

    def get_summarize_retry(self, document_content: str, last_sumarize: str) -> str:
        """通过LLM对文档内容（原始长文本）进行总结并按XML格式输出的总结内容。
        当LLM对上一次的总结内容不符合要求时，需调用该方法尝试重新总结。

        Args:
            document_content (str): 文档内容
            last_sumarize (str): 上一次总结的内容

        Returns:
            str: 生成的以文档内容进行总结的Repository描述信息
        """
        chat_completion = self.llm.chat.completions.create(
            model=self.model,
            temperature=0.7,
            messages=[
                {"role": "system",
                    "content": "你是一个文档总结助手，用中文输出总结的内容，并使用XML格式化返回的内容，生成的内容以示例为准，不需要生成其他标签的内容。示例：\
                        ```xml<Repository> \
                        <name>(该Repository的名称)</name> \
                        <owner>(该Repository的作者)</owner> \
                        <url>(该Repository的Github链接)</url> \
                        <descrpition>(... 结合提供文档信息进行分析，生成一段对于该Repository描述，描述必须包括其实现的功能、适用的应用场景等具有关键性、相关性的内容。 ...)</descrpition> \
                        <keywords>(... 根据提供文档信息生成关于该Repository合适的中文关键字。关键词之间应以逗号隔开。 ...)</keywords> \
                        </Repository>```"},
                {"role": "user",
                    "content": "```markdown(... partial document content ...)```"},
                {"role": "assistant",
                    "content": "```xml<Repository> \
                        <name>(该Repository的名称)</name> \
                        <owner>(该Repository的作者)</owner> \
                        <url>(该Repository的Github链接)</url> \
                        <descrpition>(... 结合提供文档信息进行分析，生成一段对于该Repository描述，描述必须包括其实现的功能、适用的应用场景等具有关键性、相关性的内容。 ...)</descrpition> \
                        <keywords>(... 根据提供文档信息生成关于该Repository合适的中文关键字。关键词之间应以逗号隔开。 ...)</keywords> \
                        </Repository>```"},
                {"role": "user", "content": f"```markdown{document_content}```"},
                {"role": "assistant",
                    "content": f"{last_sumarize}"},
                {"role": "user", "content": f"你回复的总结内容中需要必须包含\
                    <Repository><name><owner><url><descrpition><keywords>这几个标签和内容，请重新总结，并按照之前约定的格式进行回复。"},
            ]
        )
        assistant_generate_message = chat_completion.choices[0].message.content
        return assistant_generate_message

    def get_appropriate_repositories(self, documents: List[str], requirement: str) -> str:
        """通过LLM评估并选择能够解决需求的Repositories，并按XML格式进行输出内容。

        Args:
            documents (List[str]): 一至多个文档的内容（对原始长文本总结生成的内容）
            requirement (str): 对问题或需求的描述

        Returns:
            str: 对一至多个Repositories的描述信息
        """
        documents_content = "\n".join(
            [parse.xml_message_pre_process(doc) for doc in documents])
        chat_completion = self.llm.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system",
                    "content": "首先，你需要对这些Repositories进行分析，理解它们实现的功能以及发现它们可能的应用场景。\
                        最后，能够根据我的提问或要求，对这些Repositories进行评估，从中选择并按格式输出那些能够解决我的问题、达到我的要求的、合适的Repositories。\
                        如果不存在任何的Repository或者没有合适的Repository，则只需返回'```xml<Repositories></Repositories>```'。"},
                {"role": "user",
                    "content": f"<Repositories>(... nothing ...)</Repositories>"},
                {"role": "assistant",
                    "content": f"```xml<Repositories></Repositories>```"},
                {"role": "user",
                    "content": f"<Repositories>(... {documents_content} ...)</Repositories>"},
                {"role": "assistant",
                    "content": "好的，我已经对这些Repositories都进行分析，并且充分地理解它们实现的功能以及发现它们可能的应用场景。具体如下： \
                        ```xml<Repositories> \
                        <Repository> \
                        <name>(该Repository的名称)</name> \
                        <owner>(该Repository的作者)</owner> \
                        <url>(该Repository的Github链接)</url> \
                        <descrpition>(... 结合提供文档信息进行分析，生成一段对于该Repository描述，描述必须包括其实现的功能、适用的应用场景等具有关键性、相关性的内容。 ...)</descrpition> \
                        <keywords>(... 根据提供文档信息生成关于该Repository合适的中文关键字。关键词之间应以逗号隔开。 ...)</keywords> \
                        </Repository> ... ( ... one or more repositories ...)\
                        </Repositories>```"},
                {"role": "user",
                    "content": f"我的提问或要求是：{requirement}， \
                        你需要从这些Repositories中选择并按格式输出那些能够解决我的问题、达到我的要求的、合适的Repositories。回复的内容格式如下：\
                        ```xml<Repositories> \
                        <Repository> \
                        <name>(该Repository的名称)</name> \
                        <owner>(该Repository的作者)</owner> \
                        <url>(该Repository的Github链接)</url> \
                        <descrpition>(... 结合上下文进行分析，生成一段对于该Repository描述，描述必须包括其实现的功能、适用的应用场景等具有关键性、相关性的内容。 ...)</descrpition> \
                        <keywords>(... 根据上下文信息生成关于该Repository合适的中文关键字。关键词之间应以逗号隔开。 ...)</keywords> \
                        </Repository> ... ( ... one or more repositories ...)\
                        </Repositories>```"}
            ]
        )
        assistant_generate_message = chat_completion.choices[0].message.content
        return assistant_generate_message

    def get_retriever_prompt(self, prompt: str) -> str:
        """将用户输入的提示词翻译成中文和英文，并且提取关键字或实体，用于向量检索。

        Args:
            prompt (str): 用户输入的提示词

        Returns:
            str: 用于向量检索的提示词
        """
        chat_completion = self.llm.chat.completions.create(
            model=self.model,
            temperature=0.3,
            messages=[
                {"role": "system",
                    "content": "你是一个翻译助手，能够将我输入的内容进行翻译，生成中文和英文两种翻译结果，\
                        并且能够提取中文翻译和英语翻译两个句子中的关键词和实体信息。"},
                {"role": "user",
                    "content": "'有哪些使用了通用大模型的应用可以用于文本转语音或语音转文本的转换？'"},
                {"role": "assistant",
                    "content": "有哪些使用了通用大模型的应用可以用于文本转语音或语音转文本的转换？ \
                        （大模型、文本、语音、转换、文本转语音、语音转文本） \
                        What applications that use general large models are available for text-to-speech or speech-to-text conversion? \
                        (large models, text, speech, text-to-speech, speech-to-text, conversion)"},
                {"role": "user",
                    "content": "'What applications that use general large models are available for text-to-speech or speech-to-text conversion?'"},
                {"role": "assistant",
                    "content": "有哪些使用了通用大模型的应用可以用于文本转语音或语音转文本的转换？ \
                        （大模型、文本、语音、转换、文本转语音、语音转文本） \
                        What applications that use general large models are available for text-to-speech or speech-to-text conversion? \
                        (large models, text, speech, text-to-speech, speech-to-text, conversion)"},
                {"role": "user",
                    "content": f"'{prompt}'"},
            ]
        )
        assistant_generate_message = chat_completion.choices[0].message.content
        return assistant_generate_message
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

GITHUB_RESPONSE_SUCCESS_CODE = 200

GITHUB_RESPONSE_ERROR_CODES = {
    304: "Not modified | 资源未被修改，可以使用缓存。",
    401: "Requires authentication | 请求需要身份验证，请检查你的认证信息。",
    403: "Forbidden | 服务器拒绝请求，你没有权限访问该资源。",
    404: "Resource not found | 请求的资源不存在。",
    422: "Validation failed, or the endpoint has been spammed. | 请求验证失败，或者端点已被废弃。"
}


def get_auth_headers(auth_token: str = os.getenv('GITHUB_TOKEN')):
    headers = {
        'Accept': "application/vnd.github+json",
        'Authorization': f"Bearer {auth_token}",
        'X-GitHub-Api-Version': "2022-11-28"
    }
    return headers


# 增加重试机制，防止请求github数据时由于网络稳定性不佳而导致获取失败。
def create_session_with_retries(retries=3, backoff_factor=0.3, status_forcelist=GITHUB_RESPONSE_ERROR_CODES.keys()):
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get_username(auth_token: str = os.getenv('GITHUB_TOKEN')):
    url = "https://api.github.com/user"
    session = create_session_with_retries()
    response = session.get(url, headers=get_auth_headers(auth_token))
    data = response.json()
    return data["login"]


class Repository(BaseModel):
    owner: str = Field(default="", description="The owner of the repository.")
    name: str = Field(default="", description="The name of the repository.")
    description: str = Field(default="The repository has no description.",
                             description="A simple description of the repository.")
    stargazers_count: int = Field(
        default=0, description="Indicates how many people have collected the repository.")
    url: str = Field(default="", description="The url of the repository.")
    # There is no detailed introduction to the contents of the repository.
    readme_content: str = Field(
        default="", description="A detailed introduction of the repository. Parse content in Markdown format. Some of the content needs to be parsed in HTML format.")

    def get_readme_content(self) -> str:
        url = f"https://api.github.com/repos/{self.owner}/{self.name}/readme"
        headers = get_auth_headers()
        headers['Accept'] = "application/vnd.github.raw+json"
        # Returns the raw file contents. This is the default if you do not specify a media type.
        session = create_session_with_retries()
        try:
            response_raw = session.get(url, headers=headers, stream=False)
            response_raw.raise_for_status()  # 确保引发 HTTPError 如果响应状态码不是 2xx
        except requests.exceptions.RequestException as e:
            print(f"Request Exception: {e}")
        except AttributeError as e:
            print(
                f"Request Runtime Error - Attribute not found | It may be caused by the requested resource not existing: {e}")
        else:
            self.readme_content = response_raw.text
        return self.readme_content

    def model_dump_markdown(self) -> str:
        if self.readme_content == "":
            self.readme_content = self.get_readme_content()
        markdown_content_list = []
        for field_name, info in self.model_fields.items():
            field_value = getattr(self, field_name)
            field_description = info.description
            markdown_content_list.append(
                f"# {field_name} ({field_description})\n{field_value}")
        return "\n".join(markdown_content_list)


def get_starred_repository() -> List[Repository]:
    url = "https://api.github.com/user/starred"
    params = {
        'per_page': 100,  # 每页最多100个项目
        'page': 1         # 从第一页开始
    }

    session = create_session_with_retries()
    starred_repositories_data = []
    while True:
        response = session.get(url, headers=get_auth_headers(), params=params)
        data = response.json()
        if data:
            starred_repositories_data.extend(data)
            params['page'] += 1  # 请求下一页
        else:
            break

    starred_repositories: List[Repository] = []
    for data in starred_repositories_data:
        owner = data['owner']['login']
        name = data['name']
        description = data['description'] if data['description'] else ""
        # discarded Reason: use API to get readme-content lazy.
        stargazers_count = data['stargazers_count']
        # readme_url = "/".join([data['html_url'], "blob", data['default_branch'],"README.md?raw=true"])
        url = data['html_url']
        if data['disabled']:
            # GitHub Repository disabled == true 表示仓库已被其所有者或 GitHub 官方禁用。
            print(
                f"The repository '{owner}/{name}' has been officially disabled by its owner or GitHub")
        else:
            repository = Repository(owner=owner, name=name, description=description,
                                    stargazers_count=stargazers_count, url=url)
            starred_repositories.append(repository)
    return starred_repositories


def save_repositories_as_json(repositories: List[Repository], directory: str) -> None:
    if not os.path.exists(directory):
        os.makedirs(directory)

    for repo in repositories:
        repo.readme_content = repo.get_readme_content()
        file_path = os.path.join(directory, f"{repo.name}.json")
        with open(file_path, 'w', encoding='utf-8') as json_file:
            json_file.write(repo.model_dump_json())
        print(f"Saved {repo.owner}/{repo.name} to {file_path}")


def save_repositories_readme_as_markdown(repositories: List[Repository], directory: str, re_save: bool = False) -> None:
    if not os.path.exists(directory):
        os.makedirs(directory)

    for repo in repositories:
        file_path = os.path.join(directory, f"{repo.name}.md")
        if re_save or (not os.path.exists(file_path)):
            repo.readme_content = repo.get_readme_content()
            with open(file_path, 'w', encoding='utf-8') as json_file:
                json_file.write(repo.model_dump_markdown())
        print(f"Saved {repo.owner}/{repo.name} to {file_path}")

import os
import re
import glob
import json
import xml.etree.ElementTree as ET


def get_md_files_dict(directory: str) -> dict[str, str]:
    """获取文档的文件名和内容并存储为键值对

    Args:
        directory (str): 文档的本地存储目录

    Returns:
        dict[str, str]: 文档的文件名和内容的键值对
    """
    md_files = glob.glob(os.path.join(directory, '**/*.md'), recursive=True)
    res = {}
    for md_file in md_files:
        with open(md_file, 'r', encoding='utf-8') as file:
            content = file.read()
            res[md_file] = content
    return res


def repositories_xml2json_out_parse(xml_content: str, is_dumps=False) -> str | dict[str, list]:
    """将XML格式描述的文本转换成Json格式

    Args:
        xml_content (str): XML格式描述的文本
        is_dumps (bool, optional): 是否返回Json格式描述的字符串. Defaults to False.

    Returns:
        str | dict[str, list]: Json格式描述的字符串或Json格式的数据。
    """
    # 解析XML字符串
    root = ET.fromstring(xml_content)
    # 构建JSON结构
    repositories = []
    for repo in root:
        repo_dict = {
            'name': repo.find('name').text,
            'owner': repo.find('owner').text,
            'url': repo.find('url').text,
            'description': repo.find('description').text,
            'keywords': repo.find('keywords').text
        }
        repositories.append(repo_dict)
    # 构建最终的JSON对象
    json_result = {
        "Repositories": repositories
    }
    if is_dumps:
        # 将结果转换为JSON字符串
        json_result = json.dumps(json_result, ensure_ascii=False, indent=2)
    return json_result


def xml_message_pre_process(message: str) -> str:
    """解析回复的格式化信息，获取主要内容

    Args:
        message (str): 格式化信息，主要内容被```xml和```包裹

    Returns:
        str: 主要内容
    """
    pattern = r"```xml(.*?)```"
    match = re.search(pattern, message, re.DOTALL)
    if match:
        message = match.group(1).strip()
    else:
        message = ""
    return message


def repository_summary_vaild(content: str) -> bool:
    """判断对repository的总结内容是否符合要求，需要包含要求的标签和内容

    Args:
        content (str): repository的总结内容

    Returns:
        bool: 符合返回True否则返回False
    """
    tags_primary = ["<Repository>", "<name>", "<owner>",
                    "<url>", "<description>", "<keywords>"]
    return all(element in content for element in tags_primary)


if __name__ == "__main__":
    content = """
    ```xml
    <Repository>
        <name>1000UserGuide</name>
        <owner>naxiaoduo</owner>
        <url>https://github.com/naxiaoduo/1000UserGuide</url>
        <description>
            1000UserGuide是一个为独立开发者和创业者量身打造的资源平台，旨在帮助他们在产品推广和早期用户获取方面取得成功。该平台整合了300多个国内外推广渠道，为 用户提供了多样化的推广选择，助力用户找到目标用户群体，提升产品知名度和市场占有率。
        </description>
        <keywords>早期用户获取, 独立开发者, 创业者, 产品推广, 渠道资源</keywords>
    </Repository>
    ```
    """
    print(repository_summary_vaild(content))

"""Bounded reads of repository-linked documentation on supported public hosts."""
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit
import httpx

HOSTS = {'docs.langchain.com', 'python.langchain.com', 'docs.llamaindex.ai',
         'docs.haystack.deepset.ai', 'docs.n8n.io', 'docs.dify.ai'}


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.hidden=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript'): self.hidden += 1
        if tag in ('p','div','li','h1','h2','h3','br'): self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript'): self.hidden=max(0,self.hidden-1)
    def handle_data(self, data):
        if not self.hidden:self.parts.append(data)


def linked_urls(runtime, repository):
    urls=set()
    for source in runtime.sources.values():
        if source['repository'] == repository and source['kind'] in ('readme','documentation'):
            for url in re.findall(r'https://[^\s<>"\)]+',source['text']):
                parsed=urlsplit(url)
                if parsed.hostname in HOSTS and not parsed.username and not parsed.password and parsed.port in (None,443):
                    urls.add(url.split('#')[0])
    return sorted(urls)


def read_page(runtime, repository, url):
    if url not in linked_urls(runtime,repository):
        raise ValueError('仅可读取当前仓库资料已链接的受支持官方文档 URL；不支持任意地址或跳转')
    runtime.guard()
    if runtime.http_calls >= 60:raise TimeoutError('网络请求预算已耗尽')
    runtime.http_calls += 1
    with httpx.Client(timeout=15,follow_redirects=False,trust_env=True) as client:
        with client.stream('GET',url,headers={'User-Agent':'RepoScout/0.1','Accept':'text/html,text/plain'}) as response:
            response.raise_for_status()
            content_type=response.headers.get('content-type','')
            if not any(t in content_type for t in ('text/html','text/plain','text/markdown')):
                raise ValueError('官方文档响应不是支持的文本格式')
            body=bytearray()
            for chunk in response.iter_bytes():
                runtime.guard();body.extend(chunk)
                if len(body)>1_000_000:raise ValueError('官方文档超过 1 MB 上限')
    text=body.decode('utf-8',errors='replace')
    if 'text/html' in content_type:
        parser=TextParser();parser.feed(text);text=''.join(parser.parts)
    if not text.strip():raise ValueError('官方文档没有可读取正文')
    return runtime.add_source(repository,'official_page',url,url,text,
        metadata={'authority':'repository-linked-supported-host','version_unpinned':True,'content_type':content_type})

"""Exact source coordinates; never fuzzy-match or rewrite a quotation."""
import re


def segments(source_id, text, offset=0):
    # Keep each selectable span under the existing 1,200-character evidence limit.
    return [{'span_id': f'{source_id}:{offset+i}:{offset+i+len(text[i:i+700])}',
             'offset': offset+i, 'text': text[i:i+700]}
            for i in range(0, len(text), 700)]


def resolve(source, quote='', span_id=''):
    if span_id:
        match = re.fullmatch(r'(S\d+):(\d+):(\d+)', span_id)
        if not match or match[1] != source['id']:
            raise ValueError('片段编号与来源不匹配')
        start, end = int(match[2]), int(match[3])
        if not 0 <= start < end <= len(source['text']) or end-start > 1200:
            raise ValueError('片段范围无效或超过 1200 字符')
        original = source['text'][start:end]
        if quote and quote != original:
            raise ValueError('同时提供的摘录与片段不一致；请只选 span_id')
        return original, start
    if not quote or len(quote) > 1200 or quote not in source['text']:
        raise ValueError('摘录必须完整存在于已读取原文')
    return quote, source['text'].find(quote)

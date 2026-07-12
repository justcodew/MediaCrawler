# -*- coding: utf-8 -*-
# 豆瓣提取器单元测试(用真实豆瓣搜索 HTML,不依赖网络)

import os
import sys
from pathlib import Path

import pytest

# 确保项目根在 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from media_platform.douban.help import (
    DoubanExtractor, parse_group_url, parse_topic_url,
)


# 真实豆瓣搜索结果 HTML 片段(从 /group/search?cat=1013&q=广州租房 抓取)
SEARCH_HTML = """
<table class="olt">
<tr><td>标题</td><td>时间</td><td>回复</td><td>小组</td></tr>
<tr>
  <td><a href="https://www.douban.com/group/topic/492525633/?_spm_id=xxx" title="广州租房好难啊">广州租房好难啊</a></td>
  <td>07-01</td><td>12回复</td>
  <td><a href="https://www.douban.com/group/67019/">嫂子办</a></td>
</tr>
<tr>
  <td><a href="https://www.douban.com/group/topic/493522545/" title="求助交流｜问！广州租房">求助交流｜问！广州租房</a></td>
  <td>昨天16:02</td><td>4回复</td>
  <td><a href="https://www.douban.com/group/677543/">「人生问题」研究社</a></td>
</tr>
</table>
"""


def test_parse_topic_url():
    assert parse_topic_url("https://www.douban.com/group/topic/492525633/") == "492525633"
    assert parse_topic_url("https://www.douban.com/group/topic/492525633/?_spm_id=abc") == "492525633"
    assert parse_topic_url("492525633") == "492525633"
    with pytest.raises(ValueError):
        parse_topic_url("https://example.com/other")


def test_parse_group_url():
    g = parse_group_url("https://www.douban.com/group/guangzhou/")
    assert g.group_id == "guangzhou"
    g2 = parse_group_url("https://www.douban.com/group/5xx/")
    assert g2.group_id == "5xx"
    g3 = parse_group_url("guangzhou")
    assert g3.group_id == "guangzhou"


def test_extract_search_results():
    """从搜索 HTML 提取帖子列表"""
    ext = DoubanExtractor()
    results = ext.extract_search_results(SEARCH_HTML, keyword="广州租房")
    assert len(results) == 2
    # 第一条
    r1 = results[0]
    assert r1.topic_id == "492525633"
    assert r1.title == "广州租房好难啊"
    assert r1.reply_count == 12
    assert r1.group_id == "67019"
    assert r1.group_name == "嫂子办"
    assert r1.create_date_time == "07-01"
    assert r1.source_keyword == "广州租房"
    # 第二条
    r2 = results[1]
    assert r2.topic_id == "493522545"
    assert r2.reply_count == 4
    assert r2.group_name == "「人生问题」研究社"


def test_extract_search_results_empty():
    """空/无结果 HTML"""
    ext = DoubanExtractor()
    assert ext.extract_search_results("<html></html>") == []
    assert ext.extract_search_results("") == []


# 帖子详情页 HTML 片段(模拟豆瓣帖子结构)
TOPIC_HTML = """
<html><body>
<div class="article">
  <h1>广州租房好难啊</h1>
  <div class="topic-content">
    <div class="topic-doc">
      <div class="topic-content">在广州找房找了好久，越秀区的两房真的太难找了。</div>
    </div>
  </div>
  <h3><span class="author"><a href="https://www.douban.com/people/abc123/">小明</a></span></h3>
  <span class="create-time">2025-07-01 14:30:00</span>
</div>
<div id="comments">
  <div class="comment-item" id="comment-1001">
    <h4><a href="https://www.douban.com/people/def456/">小红</a></h4>
    <span class="pubtime">2025-07-01 15:00:00</span>
    <p class="reply-content">确实难找，建议看公园前附近</p>
  </div>
  <div class="comment-item" id="comment-1002">
    <h4><a href="https://www.douban.com/people/ghi789/">老王</a></h4>
    <span class="pubtime">2025-07-01 16:00:00</span>
    <p class="reply-content">越秀两房均价2500左右</p>
  </div>
</div>
</body></html>
"""


def test_extract_topic_detail():
    ext = DoubanExtractor()
    note = ext.extract_topic_detail(TOPIC_HTML, topic_id="492525633")
    assert note is not None
    assert note.topic_id == "492525633"
    assert note.title == "广州租房好难啊"
    assert "越秀区的两房" in note.desc
    # 作者脱敏(不存原始昵称)
    assert note.user_nickname  # 非空
    assert "小明" not in note.user_nickname  # 已脱敏
    assert note.creator_hash  # 匿名哈希非空
    assert note.create_date_time == "2025-07-01 14:30:00"


def test_extract_comments():
    ext = DoubanExtractor()
    comments = ext.extract_comments(TOPIC_HTML, topic_id="492525633")
    assert len(comments) == 2
    c1 = comments[0]
    assert c1.comment_id == "1001"
    assert c1.topic_id == "492525633"
    assert "公园前" in c1.content
    assert c1.user_nickname  # 脱敏后非空
    assert c1.create_date_time == "2025-07-01 15:00:00"

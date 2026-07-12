# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1

from enum import Enum


class SearchSortType(Enum):
    """豆瓣小组搜索排序(豆瓣搜索结果默认按相关度,排序选项有限)"""
    DEFAULT = "relevance"

# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 断点续爬模块
# 用法:
#   from checkpoint import CheckpointManager
#   manager = CheckpointManager(task_id, platform, enabled=resume_flag)
#   state = await manager.begin_scope(keyword)
#   start_page = state.last_page + 1
#   ...
#   await manager.save_page(keyword, page, note_ids, search_id=...)

from checkpoint.manager import CheckpointManager, ScopeState
from checkpoint import store

__all__ = ["CheckpointManager", "ScopeState", "store"]

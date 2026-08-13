# Third-party notices

## WeChat formal publish template

The formal publish configuration template in `frontend/src/wechatPublishTemplate.ts` and the four built-in themes in `backend/src/content_ops/themes.py` are adapted from [aiworkskills/wechat-article-skills](https://github.com/aiworkskills/wechat-article-skills), Copyright 2025 AI Work Skills, licensed under the Apache License, Version 2.0.

The imported visual sources are `default.yaml` (经典蓝), `grace.yaml` (优雅紫), `modern.yaml` (暖橙), and `simple.yaml` (极简黑), under `skills/aws-wechat-article-formatting/references/presets/themes/`. They are ported to this project's inline HTML component renderer, preserving their color, typography, headings, quotations, code blocks, lists, dividers, and image treatments.

The adaptation keeps this project's account selection, permanent cover media ID, idempotent delivery records, and global publish switch. It does not copy or bundle upstream credentials or scripts.
# ============================================
  # 1. Claude Code CLI 主缓存 (~/.claude/)
  # ============================================
  rm -rf ~/.claude/cache
  rm -rf ~/.claude/session-env
  rm -rf ~/.claude/sessions
  rm -rf ~/.claude/shell-snapshots
  rm -rf ~/.claude/file-history
  rm -rf ~/.claude/paste-cache
  rm -rf ~/.claude/backups
  rm -rf ~/.claude/usage-data
  rm -rf ~/.claude/debug
  rm -rf ~/.claude/telemetry
  rm -rf ~/.claude/tasks
  rm -rf ~/.claude/channels
  rm -rf ~/.claude/ide
  rm -rf ~/.claude/plans
  rm -rf ~/.claude/todos
  rm -rf ~/.claude/projects/*/0220a05c-6d1f-452b-b782-fb4543d67ae6  # 某些 session 缓存

  # 保留 settings.json 和 settings.local.json（你的配置）
  # 保留 hooks/（你的自定义 hooks）
  # 保留 plugins/（插件市场）
  # 保留 skills/（skills 配置）
  # 保留 history.jsonl（如不需要历史对话）

  # ============================================
  # 2. Claude Desktop App 缓存 (~/Library/Application Support/Claude/)
  # ============================================
  rm -rf ~/Library/Application\ Support/Claude/Cache
  rm -rf ~/Library/Application\ Support/Claude/Code\ Cache
  rm -rf ~/Library/Application\ Support/Claude/DawnGraphiteCache
  rm -rf ~/Library/Application\ Support/Claude/DawnWebGPUCache
  rm -rf ~/Library/Application\ Support/Claude/GPUCache
  rm -rf ~/Library/Application\ Support/Claude/IndexedDB
  rm -rf ~/Library/Application\ Support/Claude/Local\ Storage
  rm -rf ~/Library/Application\ Support/Claude/Session\ Storage
  rm -rf ~/Library/Application\ Support/Claude/Shared\ Dictionary
  rm -rf ~/Library/Application\ Support/Claude/SharedStorage
  rm -rf ~/Library/Application\ Support/Claude/WebStorage
  rm -rf ~/Library/Application\ Support/Claude/crashpad
  rm -rf ~/Library/Application\ Support/Claude/local-agent-mode-sessions
  rm -rf ~/Library/Application\ Support/Claude/vm_bundles
  rm -rf ~/Library/Application\ Support/Claude/sentry
  rm -rf ~/Library/Application\ Support/Claude/claude-code
  rm -rf ~/Library/Application\ Support/Claude/claude-code-vm

  # 保留 claude_desktop_config.json（MCP 配置）
  # 保留 config.json（OAuth token 等）

  # ============================================
  # 3. Claude Desktop 浏览器数据
  # ============================================
  rm -rf ~/Library/Application\ Support/Claude/Cookies
  rm -rf ~/Library/Application\ Support/Claude/Cookies-journal
  rm -rf ~/Library/Application\ Support/Claude/Network\ Persistent\ State
  rm -rf ~/Library/Application\ Support/Claude/Trust\ Tokens
  rm -rf ~/Library/Application\ Support/Claude/Trust\ Tokens-journal
  rm -rf ~/Library/Application\ Support/Claude/Preferences

  # ============================================
  # 4. 确认清理完成
  # ============================================
  echo "清理完成！确认关键目录状态："
  echo "--- ~/.claude/ ---"
  ls ~/.claude/
  echo ""
  echo "--- ~/Library/Application Support/Claude/ ---"
  ls ~/Library/Application\ Support/Claude/
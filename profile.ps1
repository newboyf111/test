# 设置 PowerShell 输出编码为 UTF-8
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding

# Git 配置
git config --global core.quotepath false
git config --global i18n.commitencoding utf-8
git config --global i18n.logoutputencoding utf-8

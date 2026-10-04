@echo off
REM 正典仓库一键推送脚本
REM 使用方法：注册/登录 GitHub 后，在 github.com 新建一个空仓库（建议名：decision-system，
REM 不要勾选 README 初始化），把下面两行的 "你的用户名" 替换掉，然后双击运行本文件。

set GH_USER=你的用户名
set REPO=decision-system

cd /d "E:\Documents\lingxi-claw\20261002-14-24-38-883\正典仓库"
git remote add origin https://github.com/%GH_USER%/%REPO%.git 2>nul
git branch -M main
git push -u origin main --tags

echo.
echo 推送完成（如提示登录，浏览器窗口登录 GitHub 即可）。
pause

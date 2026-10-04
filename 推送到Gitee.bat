@echo off
REM 正典仓库一键推送（Gitee 版）
REM 弹窗出现时输入 Gitee 账号 zhkrfh 的密码（或私人令牌）即可，密码不经过任何第三方。

cd /d "E:\Documents\lingxi-claw\20261002-14-24-38-883\正典仓库"
git remote remove origin 2>nul
git remote add origin https://gitee.com/zhkrfh/decision-system.git
git branch -M main
git push -u origin main --tags

echo.
echo 推送完成。请打开 https://gitee.com/zhkrfh/decision-system 核对文件与标签是否齐全。
pause

# MapYou 打包脚本
# 将Flask应用打包成Windows可执行文件

Write-Host "================================" -ForegroundColor Cyan
Write-Host "MapYou 打包工具" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# 1. 检查Python环境
Write-Host "`n[1/5] 检查Python环境..." -ForegroundColor Yellow
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: 未找到Python，请先安装Python" -ForegroundColor Red
    pause
    exit
}

# 2. 安装依赖
Write-Host "`n[2/5] 安装必要的依赖包..." -ForegroundColor Yellow
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if ($LASTEXITCODE -ne 0) {
    Write-Host "警告: 部分依赖安装失败，继续..." -ForegroundColor Yellow
}

# 3. 清理旧的打包文件
Write-Host "`n[3/5] 清理旧的打包文件..." -ForegroundColor Yellow
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "*.spec") { 
    Get-ChildItem -Filter "*.spec" | Where-Object { $_.Name -ne "MapYou.spec" } | Remove-Item -Force
}

# 4. 开始打包
Write-Host "`n[4/5] 开始打包（这可能需要5-10分钟）..." -ForegroundColor Yellow
Write-Host "提示: 打包过程中会生成大量临时文件，请耐心等待" -ForegroundColor Gray

pyinstaller MapYou.spec --clean

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n打包失败！" -ForegroundColor Red
    pause
    exit
}

# 5. 检查打包结果
Write-Host "`n[5/5] 检查打包结果..." -ForegroundColor Yellow
$exePath = "dist\MapYou-福州社区便利度分析.exe"
if (Test-Path $exePath) {
    $size = (Get-Item $exePath).Length / 1MB
    Write-Host "`n✓ 打包成功！" -ForegroundColor Green
    Write-Host "文件位置: $exePath" -ForegroundColor Green
    Write-Host "文件大小: $($size.ToString('0.00')) MB" -ForegroundColor Green
    Write-Host "`n================================" -ForegroundColor Cyan
    Write-Host "使用说明:" -ForegroundColor Cyan
    Write-Host "1. 将 dist 文件夹中的 exe 文件发送给用户" -ForegroundColor White
    Write-Host "2. 用户双击 exe 即可启动" -ForegroundColor White
    Write-Host "3. 程序会自动打开浏览器访问地图界面" -ForegroundColor White
    Write-Host "================================" -ForegroundColor Cyan
} else {
    Write-Host "`n打包失败：未找到生成的exe文件" -ForegroundColor Red
}

Write-Host "`n按任意键退出..."
pause

# Pyinstallerを使ったやり方
cd app
flet pack client.py

# fletのビルド機能でのやり方
cd app
flet build [windows | apk] --module-name client

# nuitkaでのビルド
cd app
nuitka --onefile --windows-console-mode=attach client.py
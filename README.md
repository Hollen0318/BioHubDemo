pyinstaller --noconfirm --clean --onefile \
  --add-data "templates:templates" \
  --hidden-import "engineio.async_drivers.threading" \
  main.py

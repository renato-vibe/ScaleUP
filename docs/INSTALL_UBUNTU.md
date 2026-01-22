# Instalacion en Ubuntu (robusta y rapida)

## Ruta recomendada (produccion): .deb offline + instalador GUI
1) Construye el paquete offline en una maquina con Internet.
```sh
DEB_ARCH=amd64 TARGET_PLATFORM=manylinux2014_x86_64 PYTHON_VERSION=310 \
  bash scripts/build_deb_offline.sh
```
2) Si quieres instalacion mas rapida en el servidor, genera un venv prearmado:
```sh
BUILD_PREBUILT_VENV=1 DEB_ARCH=amd64 TARGET_PLATFORM=manylinux2014_x86_64 PYTHON_VERSION=310 \
  bash scripts/build_deb_offline.sh
```
3) En `ejecutable/` quedan estos archivos:
- `ScaleUP-Installer.deb`
- `ScaleUP-Installer.run`
- `ScaleUP-Installer.desktop`
- `scaleup_installer.sh`
- `scaleup.png`
4) En el servidor destino, haz doble click en `ScaleUP-Installer.desktop` o ejecuta:
```sh
./ScaleUP-Installer.run
```

Verificacion:
```sh
scale-vision install-check --config /etc/scale-vision/config.json
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/last-decision
```

## Ruta rapida desde Git (terminal)
1) Clona y entra al repo:
```sh
git clone <URL_DEL_REPO> ~/scaleup
cd ~/scaleup
```
2) Instala como servicio systemd con:
```sh
sudo bash scripts/install_from_git.sh
```
3) Para actualizar: `git pull` y vuelve a ejecutar el script.

Desinstalacion manual (si instalaste desde Git):
```sh
sudo systemctl stop scale-vision.service
sudo systemctl disable scale-vision.service
sudo rm -rf /opt/scale-vision /etc/scale-vision /var/lib/scale-vision /var/log/scale-vision
sudo rm -f /usr/local/bin/scale-vision /etc/systemd/system/scale-vision.service
sudo userdel -r scalevision 2>/dev/null || true
sudo systemctl daemon-reload
```

## UI para validar reconocimiento
La UI local esta en `http://127.0.0.1:8080/` y permite subir imagen/video o capturar snapshot para validar reconocimiento.

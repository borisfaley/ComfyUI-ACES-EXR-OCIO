# ComfyUI-ACES-EXR-OCIO
Save images and videos in ACESCg or ACES-2065-1

Активируете ваш окружение venv или Conda

## Установка

```

cd ~/ComfyUI/ustom_nodes
git clone git@github.com:borisfaley/ComfyUI-ACES-EXR-OCIO.git
conda install -c conda-forge openimageio -y
conda install -c conda-forge numpy pillow -y

```

## Варианты
```
pip install OpenImageIO
```
## Проверка 
python -c "import OpenImageIO as oiio; print('✅ OpenImageIO версия:', oiio.VERSION)"



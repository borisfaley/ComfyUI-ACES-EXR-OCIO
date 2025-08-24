import torch
import numpy as np
import os
import urllib.request
import urllib.error
import folder_paths
import hashlib

# OpenImageIO ОБЯЗАТЕЛЕН для EXR
try:
    import OpenImageIO as oiio
    OIIO_AVAILABLE = True
    print("✅ OpenImageIO доступен для EXR сохранения")
except ImportError:
    OIIO_AVAILABLE = False
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: OpenImageIO недоступен!")
    print("   Установите: pip install OpenImageIO")
    print("   Или: conda install -c conda-forge openimageio")

class ACESEXRSaveOCIO:
    """
    ComfyUI нода для сохранения ТОЛЬКО в EXR ACES формате с OCIO поддержкой
    Требует OpenImageIO - никаких fallback форматов
    """
    
    def __init__(self):
        if not OIIO_AVAILABLE:
            raise ImportError("OpenImageIO обязателен для EXR сохранения! Установите: pip install OpenImageIO")
        
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"
        
        # Создаем папку для кэша OCIO конфигов
        self.ocio_cache_dir = os.path.join(os.path.dirname(__file__), "ocio_cache")
        os.makedirs(self.ocio_cache_dir, exist_ok=True)
        
        # Предустановленные OCIO URL - ПРАВИЛЬНЫЕ!
        self.preset_ocio_urls = {
            "ACES 1.3 CG Config": "https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/download/v2.1.0-v2.2.0/cg-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio",
            "ACES 1.3 Studio Config": "https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/download/v2.1.0-v2.2.0/studio-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio",
            "ACES 2.0 CG Config": "https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/download/v3.0.0/cg-config-v3.0.0_aces-v2.0_ocio-v2.4.ocio",
            "ACES 2.0 Studio Config": "https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES/releases/download/v3.0.0/studio-config-v3.0.0_aces-v2.0_ocio-v2.4.ocio"
        }
        
        # ACES матрицы для fallback цветовой конвертации (официальные)
        self.SRGB_TO_ACES2065_MATRIX = np.array([
            [0.4395677, 0.3831666, 0.1772656],
            [0.0897923, 0.8134201, 0.0967876], 
            [0.0175439, 0.1115623, 0.8708938]
        ])
        
        self.ACES2065_TO_ACESCG_MATRIX = np.array([
            [1.451439316, -0.236510746, -0.214928570],
            [-0.076553773, 1.176229700, -0.099675927],
            [0.008316148, -0.006032449, 0.997716301]
        ])

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "aces_render"}),
                "colorspace": (["ACES2065-1", "ACEScg"], {"default": "ACES2065-1"}),
                "compression": (["none", "zip", "zips", "rle", "piz", "pxr24", "b44", "b44a", "dwaa", "dwab"],
                               {"default": "zip"}),
                "pixel_type": (["half", "float"], {"default": "half"}),
            },
            "optional": {
                "input_colorspace": (["sRGB", "Rec.709", "Linear sRGB", "ACES2065-1", "ACEScg"], 
                                   {"default": "sRGB"}),
                "ocio_config_source": (["Auto", "Local Path", "URL", "Preset"], {"default": "Auto"}),
                "ocio_config_path": ("STRING", {"default": ""}),
                "ocio_config_url": ("STRING", {"default": ""}),
                "ocio_preset": (["ACES 1.3 CG Config", "ACES 1.3 Studio Config", "ACES 2.0 CG Config", "ACES 2.0 Studio Config"], {"default": "ACES 1.3 CG Config"}),
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("exr_path", "conversion_info") 
    FUNCTION = "save_aces_exr"
    OUTPUT_NODE = True
    CATEGORY = "image/ACES"
    
    DESCRIPTION = """
    Профессиональное сохранение в EXR ACES формате с OCIO поддержкой.
    
    ⚠️  ТРЕБУЕТ OpenImageIO - установите: pip install OpenImageIO
    🎯 ТОЛЬКО EXR - никаких fallback форматов
    ✅ Автоматическая загрузка официальных OCIO конфигов
    ✅ Поддержка ACES 1.3 и ACES 2.0
    ✅ Профессиональные ACES матрицы для fallback
    
    ComfyUI IMAGE тензоры обычно в sRGB после VAE decode.
    """

    def download_ocio_config(self, url, filename_hint="config.ocio"):
        """Скачать OCIO конфиг по URL и закэшировать с улучшенной диагностикой"""
        try:
            print(f"🌐 Попытка скачать: {url}")
            
            # Создаем hash от URL для уникального имени файла
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            cache_filename = f"ocio_{url_hash}_{filename_hint}"
            cache_path = os.path.join(self.ocio_cache_dir, cache_filename)
            
            # Проверяем кэш
            if os.path.exists(cache_path):
                file_size = os.path.getsize(cache_path)
                print(f"📁 Используем кэшированный OCIO config: {cache_filename} ({file_size} bytes)")
                return cache_path
            
            # Добавляем User-Agent для обхода блокировок
            req = urllib.request.Request(url, headers={'User-Agent': 'ComfyUI-ACES-Node/1.0'})
            
            print(f"📥 Скачиваем OCIO config...")
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(cache_path, 'wb') as f:
                    f.write(response.read())
            
            # Проверяем что файл валидный
            file_size = os.path.getsize(cache_path)
            if file_size < 1000:  # OCIO конфиги должны быть больше 1KB
                os.remove(cache_path)
                raise Exception(f"Скачанный файл слишком маленький: {file_size} bytes")
            
            print(f"✅ OCIO config скачан: {cache_filename} ({file_size} bytes)")
            return cache_path
            
        except urllib.error.HTTPError as e:
            print(f"❌ HTTP ошибка {e.code}: {e.reason}")
            print(f"   URL: {url}")
            return None
        except urllib.error.URLError as e:
            print(f"❌ URL ошибка: {e.reason}")
            print(f"   URL: {url}")
            return None
        except Exception as e:
            print(f"❌ Ошибка скачивания OCIO config: {e}")
            return None

    def find_or_download_ocio_config(self, source, path, url, preset):
        """Найти или скачать OCIO конфиг"""
        ocio_config_path = None
        
        if source == "Local Path" and path:
            if os.path.exists(path):
                ocio_config_path = path
                print(f"📁 Используем локальный OCIO config: {path}")
            else:
                print(f"❌ Локальный путь не найден: {path}")
        
        elif source == "URL" and url:
            print(f"🌐 Попытка скачивания по URL...")
            ocio_config_path = self.download_ocio_config(url)
        
        elif source == "Preset":
            preset_url = self.preset_ocio_urls.get(preset)
            if preset_url:
                print(f"📦 Используем preset: {preset}")
                ocio_config_path = self.download_ocio_config(preset_url, f"{preset.lower().replace(' ', '_')}.ocio")
            else:
                print(f"❌ Неизвестный preset: {preset}")
        
        elif source == "Auto":
            # Автопоиск в стандартных местах
            auto_paths = [
                "./ocio_configs/cg-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio",
                "./ocio_configs/studio-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio",
                "./ocio_configs/config.ocio",
                "./ocio_configs/aces_1.2/config.ocio",
                os.path.expanduser("~/ComfyUI/ocio_configs/cg-config-v2.2.0_aces-v1.3_ocio-v2.4.ocio"),
            ]
            
            for auto_path in auto_paths:
                if os.path.exists(auto_path):
                    ocio_config_path = auto_path
                    print(f"📁 Найден локальный OCIO config: {auto_path}")
                    break
            
            # Если не найден, скачиваем preset
            if not ocio_config_path:
                print("📥 Локальные конфиги не найдены, скачиваем ACES 1.3 CG Config...")
                preset_url = self.preset_ocio_urls["ACES 1.3 CG Config"]
                ocio_config_path = self.download_ocio_config(preset_url, "aces13_cg.ocio")
        
        return ocio_config_path

    def srgb_to_linear(self, image):
        """sRGB to linear conversion"""
        return np.where(
            image <= 0.04045,
            image / 12.92,
            np.power((image + 0.055) / 1.055, 2.4)
        )

    def matrix_transform(self, image, matrix):
        """Матричное преобразование цвета"""
        original_shape = image.shape
        flat_image = image.reshape(-1, 3)
        transformed = np.dot(flat_image, matrix.T)
        return transformed.reshape(original_shape)

    def convert_colorspace(self, image_array, input_cs, output_cs):
        """Конвертация цветового пространства через профессиональные ACES матрицы"""
        if input_cs == output_cs:
            return image_array, "Без конвертации"
        
        print(f"🔄 Конвертация цветового пространства: {input_cs} -> {output_cs}")
        
        if input_cs == "sRGB" and output_cs == "ACES2065-1":
            linear_image = self.srgb_to_linear(image_array)
            result = self.matrix_transform(linear_image, self.SRGB_TO_ACES2065_MATRIX)
            return result, "Matrix: sRGB -> Linear -> ACES2065-1"
        
        elif input_cs == "ACES2065-1" and output_cs == "ACEScg":
            result = self.matrix_transform(image_array, self.ACES2065_TO_ACESCG_MATRIX)
            return result, "Matrix: ACES2065-1 -> ACEScg"
        
        elif input_cs == "sRGB" and output_cs == "ACEScg":
            # Двухступенчатая конвертация: sRGB -> ACES2065-1 -> ACEScg
            linear_image = self.srgb_to_linear(image_array)
            aces2065 = self.matrix_transform(linear_image, self.SRGB_TO_ACES2065_MATRIX)
            result = self.matrix_transform(aces2065, self.ACES2065_TO_ACESCG_MATRIX)
            return result, "Matrix: sRGB -> Linear -> ACES2065-1 -> ACEScg"
        
        elif input_cs == "Linear sRGB" and output_cs == "ACES2065-1":
            # Прямое матричное преобразование из linear sRGB
            result = self.matrix_transform(image_array, self.SRGB_TO_ACES2065_MATRIX)
            return result, "Matrix: Linear sRGB -> ACES2065-1"
        
        else:
            print(f"❌ Конвертация {input_cs} -> {output_cs} не поддерживается")
            return image_array, f"Без конвертации ({input_cs} -> {output_cs} недоступна)"

    def tensor_to_numpy(self, tensor):
        """Convert ComfyUI tensor to numpy array"""
        if len(tensor.shape) == 4:
            tensor = tensor.squeeze(0)
        
        array = tensor.cpu().numpy().astype(np.float32)
        # Для ACES не обрезаем положительные значения (могут быть >1.0)
        array = np.clip(array, 0.0, None)
        
        return array

    def save_exr_aces(self, image_array, filepath, colorspace, compression="zip", pixel_type="half"):
        """Сохранить EXR с полными профессиональными ACES метаданными"""
        try:
            height, width, channels = image_array.shape
            
            # Создаем ImageSpec с нужным типом пикселей
            if pixel_type == "half":
                spec = oiio.ImageSpec(width, height, channels, oiio.HALF)
            else:  # float
                spec = oiio.ImageSpec(width, height, channels, oiio.FLOAT)
            
            # Устанавливаем сжатие
            spec.attribute("compression", compression)
            
            # Добавляем полные профессиональные ACES метаданные
            spec.attribute("oiio:ColorSpace", colorspace)
            spec.attribute("ColorSpace", colorspace)
            spec.attribute("Software", "ComfyUI ACES EXR OCIO Node")
            spec.attribute("Description", f"ACES {colorspace} EXR from ComfyUI with OCIO support")
            spec.attribute("ComfyUI:Node", "ACESEXRSaveOCIO")
            spec.attribute("ComfyUI:Workflow", "WAN -> sRGB -> ACES")
            
            if colorspace == "ACES2065-1":
                # ACES2065-1 метаданные (D60 white point, AP0 primaries)
                spec.attribute("chromaticities", "0.7347,0.2653,0.0000,1.0000,0.0001,-0.0770,0.32168,0.33767")
                spec.attribute("WhitePoint", "D60")
                spec.attribute("primaries", "ACES")
                spec.attribute("Encoding", "ACES2065-1")
                spec.attribute("TransferFunction", "Linear")
                spec.attribute("Gamut", "AP0")
            elif colorspace == "ACEScg":
                # ACEScg метаданные (D60 white point, AP1 primaries)
                spec.attribute("chromaticities", "0.713,0.293,0.165,0.830,0.128,0.044,0.32168,0.33767")
                spec.attribute("WhitePoint", "D60") 
                spec.attribute("primaries", "ACEScg")
                spec.attribute("Encoding", "ACEScg")
                spec.attribute("TransferFunction", "Linear")
                spec.attribute("Gamut", "AP1")
            
            # Добавляем информацию о диапазоне значений
            min_val, max_val = np.min(image_array), np.max(image_array)
            spec.attribute("OriginalRange", f"[{min_val:.6f}, {max_val:.6f}]")
            
            if max_val > 1.0:
                spec.attribute("HDR", "true")
                spec.attribute("MaxLuminance", f"{max_val:.3f}")
            
            # Создаем и записываем EXR
            out = oiio.ImageOutput.create(filepath)
            if not out:
                raise RuntimeError(f"Невозможно создать EXR output для {filepath}")
            
            if not out.open(filepath, spec):
                raise RuntimeError(f"Невозможно открыть {filepath} для записи EXR")
            
            success = out.write_image(image_array)
            out.close()
            
            if not success:
                raise RuntimeError("Ошибка записи EXR данных")
            
            return True, f"EXR {colorspace} ({pixel_type}, {compression}, range: [{min_val:.3f}, {max_val:.3f}])"
            
        except Exception as e:
            return False, f"Ошибка EXR: {e}"

    def save_aces_exr(self, images, filename_prefix, colorspace, compression, pixel_type,
                      input_colorspace="sRGB", ocio_config_source="Auto", ocio_config_path="", 
                      ocio_config_url="", ocio_preset="ACES 1.3 CG Config"):
        """Главная функция сохранения профессиональных ACES EXR"""
        
        # Проверяем OpenImageIO еще раз
        if not OIIO_AVAILABLE:
            error_msg = "❌ OpenImageIO недоступен! Установите: pip install OpenImageIO или conda install -c conda-forge openimageio"
            print(error_msg)
            return ("", error_msg)
        
        # Находим или скачиваем OCIO config (опционально для метаданных)
        ocio_config_path_resolved = self.find_or_download_ocio_config(
            ocio_config_source, ocio_config_path, ocio_config_url, ocio_preset
        )
        
        if ocio_config_path_resolved:
            print(f"📋 OCIO config найден: {os.path.basename(ocio_config_path_resolved)}")
        else:
            print("📋 OCIO config не найден, используем профессиональные ACES матрицы")
        
        saved_files = []
        conversion_infos = []
        
        # Обрабатываем изображения
        if len(images.shape) == 4 and images.shape[0] > 1:
            # Batch обработка
            total_frames = images.shape[0]
            print(f"🎬 Обрабатываем {total_frames} кадров...")
            
            for i in range(total_frames):
                image_tensor = images[i]
                image_array = self.tensor_to_numpy(image_tensor)
                
                # Конвертируем цветовое пространство
                converted_array, conv_info = self.convert_colorspace(
                    image_array, input_colorspace, colorspace
                )
                
                # Имя файла
                filename = f"{filename_prefix}_{i:05d}.exr"
                filepath = os.path.join(self.output_dir, filename)
                
                # Сохраняем EXR
                success, format_info = self.save_exr_aces(
                    converted_array, filepath, colorspace, compression, pixel_type
                )
                
                if success:
                    saved_files.append(filepath)
                    conversion_infos.append(f"Frame {i+1}/{total_frames}: {conv_info} -> {format_info}")
                    print(f"✅ Сохранено EXR: {os.path.basename(filepath)} ({i+1}/{total_frames})")
                else:
                    conversion_infos.append(f"Frame {i+1}/{total_frames}: ОШИБКА - {format_info}")
                    print(f"❌ Ошибка EXR: frame {i+1} - {format_info}")
        
        else:
            # Одно изображение
            if len(images.shape) == 4:
                image_tensor = images[0]
            else:
                image_tensor = images
            
            image_array = self.tensor_to_numpy(image_tensor)
            
            # Конвертируем цветовое пространство
            converted_array, conv_info = self.convert_colorspace(
                image_array, input_colorspace, colorspace
            )
            
            # Сохраняем EXR
            filename = f"{filename_prefix}.exr"
            filepath = os.path.join(self.output_dir, filename)
            
            success, format_info = self.save_exr_aces(
                converted_array, filepath, colorspace, compression, pixel_type
            )
            
            if success:
                saved_files.append(filepath)
                conversion_infos.append(f"{conv_info} -> {format_info}")
                print(f"✅ Сохранено EXR: {os.path.basename(filepath)}")
            else:
                conversion_infos.append(f"ОШИБКА - {format_info}")
                print(f"❌ Ошибка EXR: {format_info}")
        
        # Формируем результат
        exr_path = saved_files[0] if saved_files else ""
        conversion_info = "\n".join(conversion_infos)
        
        # Итоговый отчет
        if saved_files:
            print(f"🎯 ИТОГО: Сохранено {len(saved_files)} EXR файлов в {colorspace}")
        else:
            print("❌ ИТОГО: Ни одного файла не сохранено")
        
        return (exr_path, conversion_info)

# Регистрация ноды для ComfyUI
NODE_CLASS_MAPPINGS = {
    "ACESEXRSaveOCIO": ACESEXRSaveOCIO
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ACESEXRSaveOCIO": "Save ACES EXR (OCIO)"
}
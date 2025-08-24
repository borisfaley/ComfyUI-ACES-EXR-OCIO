# Сохраните это как __init__.py в папке ComfyUI-ACES-EXR-OCIO

"""
ComfyUI ACES EXR OCIO Custom Node Package
Надежное сохранение в ACES цветовом пространстве с OCIO поддержкой
"""

try:
    # Попробуем импортировать из разных возможных файлов
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
    
    # Вариант 1: robust_aces_save.py (новая версия)
    try:
        from .robust_aces_save import NODE_CLASS_MAPPINGS as NCM1, NODE_DISPLAY_NAME_MAPPINGS as NDM1
        NODE_CLASS_MAPPINGS.update(NCM1)
        NODE_DISPLAY_NAME_MAPPINGS.update(NDM1)
        print("✅ Загружена robust_aces_save.py")
    except ImportError:
        pass
    
    # Вариант 2: aces_exr_save_ocio.py (старая версия)
    try:
        from .aces_exr_save_ocio import NODE_CLASS_MAPPINGS as NCM2, NODE_DISPLAY_NAME_MAPPINGS as NDM2
        NODE_CLASS_MAPPINGS.update(NCM2)
        NODE_DISPLAY_NAME_MAPPINGS.update(NDM2)
        print("✅ Загружена aces_exr_save_ocio.py")
    except ImportError:
        pass
    
    # Вариант 3: aces_exr_save.py (базовая версия)
    try:
        from .aces_exr_save import NODE_CLASS_MAPPINGS as NCM3, NODE_DISPLAY_NAME_MAPPINGS as NDM3
        NODE_CLASS_MAPPINGS.update(NCM3)
        NODE_DISPLAY_NAME_MAPPINGS.update(NDM3)
        print("✅ Загружена aces_exr_save.py")
    except ImportError:
        pass
    
    # Проверим что что-то загружено
    if not NODE_CLASS_MAPPINGS:
        raise ImportError("Не найден ни один файл с нодой")
    
    # Экспортируем для ComfyUI
    __all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
    
    print(f"✅ ACES EXR OCIO Node загружена: {len(NODE_CLASS_MAPPINGS)} нод")
    
except ImportError as e:
    print(f"❌ Ошибка импорта ACES EXR OCIO Node: {e}")
    print("📁 Проверьте что есть один из файлов:")
    print("   - robust_aces_save.py (новая версия)")
    print("   - aces_exr_save_ocio.py (с OCIO)")
    print("   - aces_exr_save.py (базовая)")
    
    # Fallback - пустые mappings чтобы ComfyUI не падал
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
    __all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

except Exception as e:
    print(f"❌ Неожиданная ошибка в ACES EXR OCIO Node: {e}")
    import traceback
    traceback.print_exc()
    
    # Fallback
    NODE_CLASS_MAPPINGS = {}
    NODE_DISPLAY_NAME_MAPPINGS = {}
    __all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# Метаданные
WEB_DIRECTORY = "./web"
__version__ = "3.0.0"
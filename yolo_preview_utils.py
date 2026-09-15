import os
import torch
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List
from skimage.transform import resize
from skimage import img_as_bool
from skimage.morphology import convex_hull_image
from ultralytics import YOLO
import streamlit as st

MODELS_DIR = Path(__file__).parent / "yolo_models"
GENERAL_MODEL_PATH = MODELS_DIR / "e50_aug.pt"
IMAGE_MODEL_PATH = MODELS_DIR / "e100_img.pt"


@st.cache_resource(show_spinner=False)
def load_yolo_models(models_dir: Optional[Path] = None):
    """Load and cache YOLO layout models in memory."""
    target_dir = models_dir or MODELS_DIR
    gen_path = target_dir / "e50_aug.pt"
    img_path = target_dir / "e100_img.pt"

    if not gen_path.exists() or not img_path.exists():
        fallback_gen = Path("d:/REDEL/YOLO DAL hf/yolo-document-layout-analysis/models/e50_aug.pt")
        fallback_img = Path("d:/REDEL/YOLO DAL hf/yolo-document-layout-analysis/models/e100_img.pt")
        if fallback_gen.exists():
            gen_path = fallback_gen
        if fallback_img.exists():
            img_path = fallback_img

    if not gen_path.exists():
        raise FileNotFoundError(f"YOLO general model missing: {gen_path}")
    if not img_path.exists():
        raise FileNotFoundError(f"YOLO image model missing: {img_path}")

    general_model = YOLO(str(gen_path))
    image_model = YOLO(str(img_path))
    return general_model, image_model


def tableConvexHull(img, masks):
    mask = np.zeros(masks[0].shape, dtype="bool")
    for msk in masks:
        temp = msk.cpu().detach().numpy()
        chull = convex_hull_image(temp)
        mask = np.bitwise_or(mask, chull)
    return mask


def cls_exists(clss, cls):
    indices = torch.where(clss == cls)
    return len(indices[0]) > 0


def empty_mask(img):
    mask = np.zeros(img.shape[:2], dtype="uint8")
    return np.array(mask, dtype=bool)


def get_predictions(model, img2, config):
    res_dict = {'status': 1, 'masks': None, 'boxes': None}
    try:
        results = model.predict(
            source=img2,
            verbose=False,
            retina_masks=config.get('rm', True),
            imgsz=config.get('sz', 640),
            conf=config.get('conf', 0.25),
            stream=True,
            classes=config.get('classes', [0, 1])
        )
        for result in results:
            if result.masks is not None and result.boxes is not None:
                res_dict['masks'] = result.masks.data
                res_dict['boxes'] = result.boxes.data
            del result
            return res_dict
        res_dict['status'] = 0
        return res_dict
    except Exception:
        res_dict['status'] = -1
        return res_dict


def extract_mask(img, masks, boxes, clss, cls):
    if not cls_exists(clss, cls):
        return empty_mask(img)
    indices = torch.where(clss == cls)
    c_masks = masks[indices]
    mask_arr = torch.any(c_masks, dim=0).bool()
    return mask_arr.cpu().detach().numpy()


def extract_img_mask(img_model, img, config):
    res_dict = {'status': 1, 'mask': empty_mask(img)}
    res = get_predictions(img_model, img, config)
    if res['status'] == -1:
        res_dict['status'] = -1
    elif res['status'] == 0 or res['masks'] is None:
        res_dict['mask'] = empty_mask(img)
    else:
        masks = res['masks']
        boxes = res['boxes']
        clss = boxes[:, 5]
        mask = extract_mask(img, masks, boxes, clss, 0)
        res_dict['mask'] = mask
    return res_dict


def get_masks(img, model, img_model, configs):
    response = {'status': 1, 'counts': {'paragraph': 0, 'text': 0, 'image': 0, 'table': 0}, 'raw_boxes': []}
    ans_masks = []

    # Get paragraph (0) and text (1) masks
    res = get_predictions(model, img, configs['paratext'])
    if res['status'] == -1:
        response['status'] = -1
        return response
    elif res['status'] == 0 or res['masks'] is None:
        for _ in range(2):
            ans_masks.append(empty_mask(img))
    else:
        masks, boxes = res['masks'], res['boxes']
        clss = boxes[:, 5]
        for cls in range(2):
            mask = extract_mask(img, masks, boxes, clss, cls)
            ans_masks.append(mask)
            if cls == 0:
                response['counts']['paragraph'] = int((clss == 0).sum().item())
            elif cls == 1:
                response['counts']['text'] = int((clss == 1).sum().item())
        if boxes is not None:
            response['raw_boxes'].extend(boxes.cpu().detach().numpy())

    # Get image (2) and table (3) masks
    res2 = get_predictions(model, img, configs['imgtab'])
    if res2['status'] == -1:
        response['status'] = -1
        return response
    elif res2['status'] == 0 or res2['masks'] is None:
        for _ in range(2):
            ans_masks.append(empty_mask(img))
    else:
        masks, boxes = res2['masks'], res2['boxes']
        clss = boxes[:, 5]

        if cls_exists(clss, 2):
            img_res = extract_img_mask(img_model, img, configs['image'])
            if img_res['status'] == 1:
                img_mask = img_res['mask']
            else:
                img_mask = empty_mask(img)
            response['counts']['image'] = int((clss == 2).sum().item())
        else:
            img_mask = empty_mask(img)
        ans_masks.append(img_mask)

        if cls_exists(clss, 3):
            indices = torch.where(clss == 3)
            tbl_mask = tableConvexHull(img, masks[indices])
            response['counts']['table'] = int((clss == 3).sum().item())
        else:
            tbl_mask = empty_mask(img)
        ans_masks.append(tbl_mask)

        if boxes is not None:
            response['raw_boxes'].extend(boxes.cpu().detach().numpy())

    if not configs['paratext']['rm']:
        h, w, _ = img.shape
        for i in range(4):
            ans_masks[i] = img_as_bool(resize(ans_masks[i], (h, w)))

    response['masks'] = ans_masks
    return response


def overlay(image, mask, color, alpha=0.4):
    """Overlay color mask on OpenCV image."""
    color_bgr = color[::-1]
    colored_mask = np.expand_dims(mask, 0).repeat(3, axis=0)
    colored_mask = np.moveaxis(colored_mask, 0, -1)
    masked = np.ma.MaskedArray(image, mask=colored_mask, fill_value=color_bgr)
    image_overlay = masked.filled()
    image_combined = cv2.addWeighted(image, 1 - alpha, image_overlay, alpha, 0)
    return image_combined


_rapid_ocr_engine = None

def get_rapid_ocr():
    """Lazy-load RapidOCR engine for layout crop text extraction."""
    global _rapid_ocr_engine
    if _rapid_ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _rapid_ocr_engine = RapidOCR()
        except Exception:
            _rapid_ocr_engine = False
    return _rapid_ocr_engine if _rapid_ocr_engine is not False else None


def extract_text_from_crop(crop_pil: Image.Image) -> str:
    """Extract text inside a cropped layout box using ONNX RapidOCR."""
    engine = get_rapid_ocr()
    if engine is None or crop_pil is None:
        return ""
    try:
        np_img = np.array(crop_pil.convert('RGB'))
        res, _ = engine(np_img)
        if not res:
            return ""
        lines = [line[1] for line in res if line and len(line) >= 2]
        return "\n".join(lines)
    except Exception:
        return ""


def get_crop_text(c_info: Dict[str, Any]) -> str:
    """Lazy extract text for a crop and cache it inside c_info to avoid redundant OCR runs."""
    if c_info is None:
        return ""
    if c_info.get("text") is None:
        c_info["text"] = extract_text_from_crop(c_info.get("crop_pil"))
    return c_info.get("text", "")


def run_yolo_layout_analysis(
    input_image: Any,
    conf_threshold: float = 0.25,
    alpha: float = 0.4,
    selected_class: Optional[str] = None
) -> Tuple[Image.Image, Dict[str, int], List[Dict[str, Any]]]:
    """
    Runs YOLO document layout analysis on a PIL Image, file path, or OpenCV image.
    Args:
        selected_class: None/'all', 'paragraph', 'text', 'image', 'table'
    Returns:
        (annotated_pil_image, counts_dict, region_crops_list)
    """
    general_model, image_model = load_yolo_models()

    if isinstance(input_image, (str, Path)):
        img_cv = cv2.imread(str(input_image))
    elif isinstance(input_image, Image.Image):
        img_cv = cv2.cvtColor(np.array(input_image.convert('RGB')), cv2.COLOR_RGB2BGR)
    elif isinstance(input_image, np.ndarray):
        img_cv = input_image.copy()
    else:
        raise ValueError(f"Unsupported image type: {type(input_image)}")

    if img_cv is None:
        raise ValueError("Could not decode image for YOLO preview")

    configs = {
        'paratext': {
            'sz': 640,
            'conf': conf_threshold,
            'rm': True,
            'classes': [0, 1]
        },
        'imgtab': {
            'sz': 640,
            'conf': max(0.2, conf_threshold),
            'rm': True,
            'classes': [2, 3]
        },
        'image': {
            'sz': 640,
            'conf': max(0.2, conf_threshold),
            'rm': True,
            'classes': [0]
        }
    }

    res = get_masks(img_cv, general_model, image_model, configs)
    if res['status'] == -1:
        for idx in configs.keys():
            configs[idx]['rm'] = False
        res = get_masks(img_cv, general_model, image_model, configs)

    color_map = {
        0: (255, 0, 0),    # Paragraph: Red
        1: (0, 255, 0),    # Text: Green
        2: (0, 0, 255),    # Image: Blue
        3: (255, 255, 0),  # Table: Yellow
    }

    class_idx_map = {
        'paragraph': 0,
        'text': 1,
        'image': 2,
        'table': 3,
    }

    filter_idx = class_idx_map.get(selected_class.lower()) if selected_class else None

    annotated_img = img_cv.copy()
    if res.get('masks'):
        for i, mask in enumerate(res['masks']):
            if mask is not None and mask.shape[:2] == annotated_img.shape[:2]:
                if filter_idx is None or filter_idx == i:
                    annotated_img = overlay(annotated_img, mask, color=color_map[i], alpha=alpha)

    # Extract cropped regions for selected class or all classes
    region_crops = []
    h_img, w_img = img_cv.shape[:2]

    # Generate cropped regions from mask contours (text is lazy-evaluated on demand)
    if res.get('masks'):
        class_names = ['paragraph', 'text', 'image', 'table']
        for i, mask in enumerate(res['masks']):
            c_name = class_names[i]
            if filter_idx is not None and filter_idx != i:
                continue
            if mask is not None and np.any(mask):
                mask_uint8 = (mask * 255).astype(np.uint8)
                contours, _ = cv2.findContours(mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                crop_idx = 1
                for cnt in contours:
                    x, y, w, h = cv2.boundingRect(cnt)
                    if w > 15 and h > 15:
                        crop = img_cv[y:y+h, x:x+w]
                        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                        crop_pil = Image.fromarray(crop_rgb)
                        region_crops.append({
                            "class_name": c_name,
                            "index": crop_idx,
                            "box": (x, y, w, h),
                            "crop_pil": crop_pil,
                            "text": None  # Lazy-loaded when requested
                        })
                        crop_idx += 1

    rgb_img = cv2.cvtColor(annotated_img, cv2.COLOR_BGR2RGB)
    pil_result = Image.fromarray(rgb_img)
    counts = res.get('counts', {'paragraph': 0, 'text': 0, 'image': 0, 'table': 0})
    return pil_result, counts, region_crops


def draw_layout_annotations(
    base_image: Any,
    crops: List[Dict[str, Any]],
    selected_crop: Optional[Dict[str, Any]] = None,
    draw_box_labels: bool = True
) -> Image.Image:
    """Draws bounding boxes, box numbers, and highlights the selected box on the layout image."""
    if isinstance(base_image, (str, Path)):
        img_cv = cv2.imread(str(base_image))
    elif isinstance(base_image, Image.Image):
        img_cv = cv2.cvtColor(np.array(base_image.convert('RGB')), cv2.COLOR_RGB2BGR)
    elif isinstance(base_image, np.ndarray):
        img_cv = base_image.copy()
    else:
        raise ValueError(f"Unsupported image type: {type(base_image)}")

    color_map_bgr = {
        'paragraph': (0, 0, 220),   # Red
        'text': (0, 200, 0),        # Green
        'image': (220, 0, 0),       # Blue
        'table': (0, 220, 220),     # Yellow
    }

    # 1. Draw all unselected boxes
    for c_info in crops:
        if selected_crop and c_info["box"] == selected_crop["box"] and c_info["class_name"] == selected_crop["class_name"]:
            continue

        x, y, w, h = c_info["box"]
        c_name = c_info["class_name"]
        color = color_map_bgr.get(c_name.lower(), (0, 200, 0))

        cv2.rectangle(img_cv, (x, y), (x + w, y + h), color, 2)
        if draw_box_labels:
            label = f"{c_name.upper()} #{c_info['index']}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(img_cv, (x, max(0, y - th - 6)), (x + tw + 6, max(th + 6, y)), (255, 255, 255), -1)
            cv2.putText(img_cv, label, (x + 3, max(th + 2, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    # 2. Draw selected box with glowing yellow/cyan highlight
    if selected_crop:
        x, y, w, h = selected_crop["box"]
        c_name = selected_crop["class_name"]

        cv2.rectangle(img_cv, (max(0, x - 4), max(0, y - 4)), (x + w + 4, y + h + 4), (0, 255, 255), 5)
        cv2.rectangle(img_cv, (x, y), (x + w, y + h), (255, 255, 0), 3)

        sel_label = f"SELECTED BOX #{selected_crop['index']} [{c_name.upper()}]"
        (tw, th), _ = cv2.getTextSize(sel_label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(img_cv, (x, max(0, y - th - 10)), (x + tw + 10, max(th + 10, y)), (0, 255, 255), -1)
        cv2.putText(img_cv, sel_label, (x + 5, max(th + 5, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)

    rgb_result = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_result)



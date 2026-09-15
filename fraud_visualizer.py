# Explainable Fraud Visualizer
# Renders the full original invoice document page with clean color-coded YOLO layout bounding boxes:
# - GREEN bounding boxes for normal / verified document areas
# - RED bold bounding boxes (with soft highlight) for suspicious / fraudulent areas (no text clutter)

import cv2
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple


def draw_fraud_layout_overlay(
    base_image: Any,
    crops: List[Dict[str, Any]],
    draw_normal_boxes: bool = True
) -> Image.Image:
    """
    Overlays clean YOLO bounding boxes on the full original invoice document.
    - Normal fields -> GREEN bounding box (clean outline, no text)
    - Fraudulent/Suspicious fields -> RED bounding box with bold highlight (no text)
    """
    if isinstance(base_image, (str, Path)):
        img_cv = cv2.imread(str(base_image))
    elif isinstance(base_image, Image.Image):
        img_cv = cv2.cvtColor(np.array(base_image.convert('RGB')), cv2.COLOR_RGB2BGR)
    elif isinstance(base_image, np.ndarray):
        img_cv = base_image.copy()
    else:
        raise ValueError(f'Unsupported image type: {type(base_image)}')

    if img_cv is None:
        raise ValueError('Could not decode image for fraud visualization')

    h_img, w_img = img_cv.shape[:2]

    # Colors in BGR
    GREEN_COLOR = (34, 197, 94)      # Vibrant Green #22c55e
    RED_COLOR = (20, 20, 239)        # Vibrant Red #ef4444
    RED_GLOW = (50, 50, 255)         # Outer Red Highlight

    # 1. First pass: Draw all normal (Green) bounding boxes
    if draw_normal_boxes:
        for c_info in crops:
            if c_info.get('is_flagged', False):
                continue  # Draw flagged ones on top in second pass

            x, y, w, h = c_info['box']
            cv2.rectangle(img_cv, (x, y), (x + w, y + h), GREEN_COLOR, 2)

    # 2. Second pass: Draw all flagged (Red) bounding boxes with bold highlight
    for c_info in crops:
        if not c_info.get('is_flagged', False):
            continue

        x, y, w, h = c_info['box']

        # Semi-transparent red fill over the suspicious region
        overlay_mask = img_cv.copy()
        cv2.rectangle(overlay_mask, (x, y), (x + w, y + h), (0, 0, 220), -1)
        cv2.addWeighted(overlay_mask, 0.18, img_cv, 0.82, 0, img_cv)

        # Outer glowing red outline
        cv2.rectangle(img_cv, (max(0, x - 2), max(0, y - 2)), (min(w_img, x + w + 2), min(h_img, y + h + 2)), RED_GLOW, 2)
        # Inner sharp red bounding box
        cv2.rectangle(img_cv, (x, y), (x + w, y + h), RED_COLOR, 3)

    rgb_result = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_result)
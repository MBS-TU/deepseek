"""Build the animated pet frames and application icon from the Feiyu reference.

Run inside the project venv (Pillow, numpy, scipy, OpenCV):

    venv\\Scripts\\python.exe tools\\build_assets.py

The reference image is never modified.  The cut-out frames are written to
assets/idle, assets/mouse, assets/key and assets/drag.  For the active hand
animations, the hand is cut out as its own layer and the keyboard/mousepad stays
fixed underneath it.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "design"
ASSETS = ROOT / "assets"

FRAME_W, FRAME_H = 700, 720
SCENE_W = 640
BASE_TOP = 36
SHADOW_ALPHA = 52
SHADOW_BLUR = 14
SHADOW_OFFSET = (0, 12)

SOURCE_FILE = DESIGN / "feiyu.png"

# Hand masks are seeded on the actual pale paws (not the warm skin threshold,
# which finds only the forearms in this illustration).
HAND_RIGHT_KEY = {
    "box": (290, 420, 475, 600),
    "fg": [(355, 535), (380, 540), (400, 535), (415, 520),
           (425, 505), (438, 480), (446, 465), (450, 452)],
    "bg": [(310, 585), (330, 585), (350, 590), (455, 585),
           (465, 555), (465, 430), (300, 445), (300, 500),
           (325, 555)],
    "min_y": 435,
}
HAND_LEFT_MOUSE = {
    "box": (60, 430, 235, 525),
    "fg": [(100, 480), (125, 485), (145, 480),
           (165, 470), (180, 478), (195, 478)],
    "bg": [(65, 510), (80, 520), (220, 500), (225, 450),
           (200, 440), (65, 455)],
    # The small mouse sits under the paw.  Include that oval patch in the
    # moving layer so the device travels with the hand; the pad itself stays
    # fixed because this patch is only slightly larger than the mouse.
    "extra_ellipse": (48, 470, 205, 550),
}


def split_hand(scene: Image.Image, spec: dict) -> tuple[Image.Image, Image.Image]:
    """Cut the active hand out and reconstruct the surface underneath.

    The pale paws are segmented with GrabCut inside a hand-specific box.  A
    simple warm-skin threshold can only find the character's forearms, which is
    why the paws used to remain painted on the desk.  Returns
    ``(hand_sticker, clean_background)``; the keyboard/mousepad stays fixed in
    the background and only the sticker moves.
    """
    arr = np.asarray(scene)
    x0, y0, x1, y1 = spec["box"]
    roi_bgr = cv2.cvtColor(arr[y0:y1, x0:x1, :3], cv2.COLOR_RGB2BGR)
    h, w = roi_bgr.shape[:2]

    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    mask[:5, :] = cv2.GC_BGD
    mask[-5:, :] = cv2.GC_BGD
    mask[:, :5] = cv2.GC_BGD
    mask[:, -5:] = cv2.GC_BGD
    for sx, sy in spec["fg"]:
        cv2.circle(mask, (sx - x0, sy - y0), 9, cv2.GC_FGD, -1)
    for sx, sy in spec["bg"]:
        cv2.circle(mask, (sx - x0, sy - y0), 9, cv2.GC_BGD, -1)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(roi_bgr, mask, None, bgd, fgd, 10, cv2.GC_INIT_WITH_MASK)

    hand = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
    roi_rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB).astype(np.int16)
    r, g, b = roi_rgb[:, :, 0], roi_rgb[:, :, 1], roi_rgb[:, :, 2]
    # Do not let the blue sleeve or the green pad/keys travel with the paw.
    blue = (b > r + 16) & (b > g + 6)
    green = (g > r + 4) & (g > b + 6) & (g > 80)
    hand[blue | green] = 0

    min_y = spec.get("min_y")
    if min_y is not None and min_y > y0:
        hand[: min_y - y0, :] = 0

    labels, _ = ndimage.label(hand, structure=np.ones((3, 3)))
    keep = np.zeros_like(hand)
    for sx, sy in spec["fg"]:
        lid = labels[sy - y0, sx - x0]
        if lid:
            keep[labels == lid] = 1
    if not keep.any():
        keep = (labels == np.argmax(np.bincount(labels.ravel())[1:]) + 1).astype(np.uint8)
    hand = keep
    hand = ndimage.binary_closing(hand, iterations=2)
    hand = ndimage.binary_dilation(hand, iterations=1).astype(np.uint8)

    full = np.zeros(arr.shape[:2], np.uint8)
    full[y0:y1, x0:x1] = hand

    ellipse = spec.get("extra_ellipse")
    extra = None
    if ellipse:
        ex0, ey0, ex1, ey1 = ellipse
        cx, cy = (ex0 + ex1) / 2, (ey0 + ey1) / 2
        rx, ry = max(1, (ex1 - ex0) / 2), max(1, (ey1 - ey0) / 2)
        yy, xx = np.ogrid[: arr.shape[0], : arr.shape[1]]
        extra = (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) <= 1.0
        full[extra] = 1

    # The sticker keeps only the paw + its ink outline.
    sticker_alpha = Image.fromarray((full * 255).astype(np.uint8))
    sticker_alpha = sticker_alpha.filter(ImageFilter.GaussianBlur(0.55))
    sticker = scene.copy()
    sticker.putalpha(sticker_alpha)

    # Remove the paw and its contact shadow from the desk, then inpaint the
    # keyboard/mousepad back into place.  This layer never moves.
    hole = ndimage.binary_dilation(full, iterations=12).astype(np.uint8) * 255
    bgr = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGB2BGR)
    inpainted = cv2.inpaint(bgr, hole, 9, cv2.INPAINT_TELEA)
    clean = np.dstack([
        cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB),
        arr[:, :, 3],
    ]).astype(np.uint8)
    clean_image = Image.fromarray(clean, "RGBA")
    if extra is not None:
        # Inpainting a patch containing the dark mouse outline produces a dark
        # crater.  The mouse travels with the paw, so fill that patch with the
        # surrounding flat pad colour instead; when the mouse slides away, the
        # exposed pad looks clean.
        pad = Image.new("RGBA", scene.size, (238, 255, 188, 255))
        fill_alpha = Image.fromarray((extra * 255).astype(np.uint8))
        fill_alpha = fill_alpha.filter(ImageFilter.GaussianBlur(1.4))
        clean_image = Image.composite(pad, clean_image, fill_alpha)
    return sticker, clean_image


def compose_hand(base: Image.Image, sticker: Image.Image,
                 dx: float, dy: float, shadow: bool = True) -> Image.Image:
    composed = base.copy()
    distance = (dx * dx + dy * dy) ** 0.5
    if shadow and distance > 4:
        # A soft contact shadow that travels with the hand makes the depth
        # separation readable even at 100x100.
        strength = min(0.42, 0.10 + distance / 190.0)
        shadow_alpha = sticker.getchannel("A").filter(ImageFilter.GaussianBlur(3))
        shadow_alpha = shadow_alpha.point(lambda v: int(v * strength))
        shadow = Image.new("RGBA", base.size, (15, 32, 45, 255))
        shadow.putalpha(shadow_alpha)
        composed.alpha_composite(shadow, (round(dx + 4), round(dy + 7)))
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.alpha_composite(sticker, (round(dx), round(dy)))
    composed.alpha_composite(layer)
    return composed


def remove_background(image: Image.Image) -> Image.Image:
    """Remove the white sheet connected to the image border.

    White parts enclosed by the green desk border (desk surface, keys) are kept.
    """
    image = image.convert("RGBA")
    rgb = np.asarray(image)[:, :, :3].astype(np.int16)
    high = rgb.min(axis=2)
    spread = rgb.max(axis=2) - rgb.min(axis=2)
    candidate = (high >= 238) & (spread <= 14)

    labels, count = ndimage.label(candidate)
    border_labels = np.unique(
        np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
    )
    border_labels = border_labels[border_labels > 0]
    background = np.isin(labels, border_labels)

    out = np.array(image)
    out[background, 3] = 0

    # A 0.6 px alpha feather hides the hardest stair steps without whitening
    # the hand-drawn outline.
    alpha = Image.fromarray(out[:, :, 3]).filter(ImageFilter.GaussianBlur(0.6))
    out[:, :, 3] = np.asarray(alpha)
    return Image.fromarray(out, "RGBA")


def crop_scene(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("no opaque pixels after background removal")
    left, top, right, bottom = bbox

    # The lower desk edge intentionally reaches the left/right borders of the
    # source.  Keep the full drawing width and just trim dead space at the top.
    left = 0
    right = image.width
    top = max(0, top - 14)
    bottom = image.height
    return image.crop((left, top, right, bottom))


def load_scene(path: Path) -> Image.Image:
    raw = Image.open(path)
    if raw.mode == "P":
        raw = raw.convert("RGBA")
    else:
        raw = raw.convert("RGBA")
    cut = remove_background(raw)
    scene = crop_scene(cut)
    ratio = scene.height / scene.width
    return scene.resize((SCENE_W, round(SCENE_W * ratio)), Image.Resampling.LANCZOS)


def fit_center(image: Image.Image, angle: float = 0.0,
               sx: float = 1.0, sy: float = 1.0) -> Image.Image:
    w = max(1, round(image.width * sx))
    h = max(1, round(image.height * sy))
    layer = image.resize((w, h), Image.Resampling.LANCZOS)
    if abs(angle) > 0.01:
        layer = layer.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    return layer


def make_frame(scene: Image.Image, *, dx: float = 0.0, dy: float = 0.0,
               angle: float = 0.0, sx: float = 1.0, sy: float = 1.0) -> Image.Image:
    layer = fit_center(scene, angle, sx, sy)
    canvas = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))

    x = round((FRAME_W - layer.width) / 2 + dx)
    y = round(BASE_TOP + (scene.height - layer.height) / 2 + dy)

    # Soft grounded shadow.  It is made from the transformed alpha so it follows
    # the pose during the little hops.
    alpha = layer.getchannel("A")
    shadow = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    shadow.putalpha(
        alpha.transform(
            (FRAME_W, FRAME_H),
            Image.Transform.AFFINE,
            (1, 0, -x, 0, 1, -y),
            resample=Image.Resampling.NEAREST,
        )
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))
    shadow.putalpha(shadow.getchannel("A").point(lambda v: int(v * SHADOW_ALPHA / 255)))
    canvas.alpha_composite(shadow, (SHADOW_OFFSET[0], SHADOW_OFFSET[1]))
    canvas.alpha_composite(layer, (x, y))
    return canvas


def build_state(name: str, scene: Image.Image, frames: list[dict]) -> None:
    target = ASSETS / name
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.png"):
        old.unlink()
    for i, params in enumerate(frames):
        frame = make_frame(scene, **params)
        frame.save(target / f"{i:02d}.png", optimize=True)
    print(f"{name:5s}: {len(frames)} frames")


def build_hand_state(name: str, base: Image.Image, sticker: Image.Image,
                     offsets: list[tuple[float, float]], shadow: bool = True) -> None:
    """Save frames with a fixed keyboard/mousepad and an independent hand."""
    target = ASSETS / name
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.png"):
        old.unlink()
    for i, (dx, dy) in enumerate(offsets):
        frame = make_frame(compose_hand(base, sticker, dx, dy, shadow=shadow))
        frame.save(target / f"{i:02d}.png", optimize=True)
    print(f"{name:5s}: {len(offsets)} frames (separated hand)")


def build_icon(pose1: Image.Image) -> None:
    # Crop the face from the clean pose and put it on a sky-blue rounded tile.
    # Values are in the 2016x2048 source coordinate system.
    head = pose1.crop((260, 90, 1810, 1640)).resize((512, 512), Image.Resampling.LANCZOS)
    tile = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    d.rounded_rectangle((8, 8, 503, 503), radius=112, fill=(230, 244, 255, 255),
                        outline=(47, 112, 166, 255), width=18)
    # A tiny circle highlight in the top-right.
    d.ellipse((390, 40, 448, 98), fill=(255, 255, 255, 150))
    tile.alpha_composite(head, (0, 0))

    mask = Image.new("L", (512, 512), 0)
    ImageDraw.Draw(mask).rounded_rectangle((18, 18, 493, 493), radius=102, fill=255)
    tile.putalpha(Image.composite(tile.getchannel("A"), Image.new("L", (512, 512), 0), mask))

    tile.resize((256, 256), Image.Resampling.LANCZOS).save(ASSETS / "icon.png")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    tile.resize((256, 256), Image.Resampling.LANCZOS).save(
        ASSETS / "icon.ico", format="ICO", sizes=sizes
    )
    print("icon  : icon.ico / icon.png")


def make_preview(state_frames: dict[str, list[Image.Image]]) -> None:
    cols = 4
    cell_w, cell_h = 245, 252
    rows = len(state_frames)
    sheet = Image.new("RGB", (cols * cell_w, rows * (cell_h + 26) + 8), (240, 247, 253))
    checker = Image.new("RGBA", (cell_w, cell_h), (255, 255, 255, 255))
    checker_draw = ImageDraw.Draw(checker)
    tile = 22
    for yy in range(0, cell_h, tile):
        for xx in range(0, cell_w, tile):
            if (xx // tile + yy // tile) % 2:
                checker_draw.rectangle((xx, yy, xx + tile - 1, yy + tile - 1),
                                       fill=(231, 238, 244, 255))
    sheet_draw = ImageDraw.Draw(sheet)
    for row, (name, frames) in enumerate(state_frames.items()):
        top = row * (cell_h + 26) + 8
        sheet_draw.rectangle((0, top, cols * cell_w, top + 22), fill=(30, 73, 110))
        sheet_draw.text((8, top + 4), name.upper(), fill=(233, 247, 255))
        picks = np.linspace(0, len(frames) - 1, cols).round().astype(int)
        for col, idx in enumerate(picks):
            bg = checker.copy()
            frame = frames[int(idx)].copy()
            frame.thumbnail((cell_w - 12, cell_h - 12), Image.Resampling.LANCZOS)
            bg.alpha_composite(frame, ((cell_w - frame.width) // 2,
                                       (cell_h - frame.height) // 2))
            sheet.paste(bg.convert("RGB"), (col * cell_w, top + 22))
    out = DESIGN / "animation_preview.png"
    sheet.save(out)
    print("preview:", out)


def main() -> None:
    if not SOURCE_FILE.exists():
        raise SystemExit("design/feiyu.png is required")

    raw_pose = Image.open(SOURCE_FILE).convert("RGBA")
    clean_pose = remove_background(raw_pose)

    scene = load_scene(SOURCE_FILE)
    key_sticker, key_base = split_hand(scene, HAND_RIGHT_KEY)
    mouse_sticker, mouse_base = split_hand(scene, HAND_LEFT_MOUSE)

    specs = {
        # The desk, keyboard and mousepad never move.  Idle is a single static
        # plate; all visible life comes from the independently layered hands.
        "idle": (scene, [{}]),
        "drag": (scene, [{}]),
    }

    for name, (state_scene, params) in specs.items():
        build_state(name, state_scene, params)

    # The keyboard and mousepad stay byte-for-byte identical across these
    # frames; only the cut-out paw moves.
    build_hand_state("mouse", mouse_base, mouse_sticker, [
        (0, 0), (8, -1), (15, 1), (20, 2),
        (13, 0), (0, -1), (-13, 0), (-20, 2),
    ], shadow=False)
    build_hand_state("key", key_base, key_sticker, [
        (0, 0), (-1, -6), (0, -13), (1, -20),
        (0, -12), (-1, -5), (0, 1), (0, 0),
    ])

    counts = {name: len(params) for name, (_, params) in specs.items()}
    counts["mouse"] = 8
    counts["key"] = 8
    all_frames: dict[str, list[Image.Image]] = {}
    for name, count in counts.items():
        all_frames[name] = [
            Image.open(ASSETS / name / f"{i:02d}.png").convert("RGBA")
            for i in range(count)
        ]

    build_icon(clean_pose)
    make_preview(all_frames)


if __name__ == "__main__":
    main()

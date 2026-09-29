# 潮汐捕手 弹头动画（TIDECAT）

3×3 格范围的潮汐冲击动画。**不属于**真实二战兰博版，没有打进那个压缩包。

| 文件 | 内容 |
| --- | --- |
| `tidecat.shp` | 30 帧，224×176，以落点为中心绘制 |
| `tidecat.pal` | 专用海水色盘（青、蓝、浪花白） |

预览：`previews/tidecat.gif`（循环播放）、`previews/tidecat_sheet.png`（逐帧）。
源码：`tools/shp/tideanim.py`，运行 `python3 tools/shp/tideanim.py 输出目录` 可重新生成。

## 过程

1. 第 0–4 帧：落点冲起水柱，同时向四周溅出水花。
2. 第 4–10 帧：一圈浪头向外推，推到 3×3 格边缘（横向半径 78 px）。
3. 第 10–20 帧：地面积水变成顺时针旋转的漩涡，中心是暗色漩涡眼。这段对应"大幅减速"。
4. 第 20–29 帧：积水从外向内碎裂、退去。

## rulesmd.ini / artmd.ini 示例

```ini
[Animations]
; 追加一行
xxx=TIDECAT

[TIDECAT]                   ; artmd.ini
CustomPalette=tidecat.pal   ; Ares：使用专用色盘
Normalized=yes
Layer=ground                ; 画在单位脚下，被减速的单位就站在漩涡里
;Translucent=yes            ; 想要半透明水面就打开

[你的近战弹头]               ; rulesmd.ini
AnimList=TIDECAT
CellSpread=1.5              ; 3×3
```

动画一共 30 帧，`Normalized=yes` 时大约播放 2 秒。如果减速持续时间跟这个对不上，把 `Rate=` 调大或调小即可。

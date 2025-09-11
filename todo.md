# Mapillary Sequence Downloader 改進 TODO

## 🎯 主要改進目標

基於與 `another_mapillary_download` 的比較分析，發現 `sequence_downloader.py` 在 GPS 精度、時區處理、EXIF 標籤等方面有顯著改進空間。

## 📊 發現的問題

### 1. 相機資訊缺失問題 ⚠️ 最高優先級

**現況：**

- API 請求中缺少 `make` 和 `model` 欄位
- 無法從 Mapillary API 獲取相機製造商和型號資訊
- EXIF 標籤中沒有相機資訊

**目標：**

- 成功寫入相機製造商（Make）和型號（Model）到 EXIF
- 與 `another_mapillary_download` 保持一致的相機資訊

**改進方案：**

- [ ] 在 API 請求欄位中添加 `make` 和 `model`
- [ ] 確保相機資訊正確寫入 EXIF 標籤
- [ ] 測試相機資訊的讀取和顯示

### 2. GPS 座標精度問題 ⚠️ 高優先級

**現況：**

- 使用 `piexif` 固定精度：1/100 = 0.01 秒
- 實際精度：±0.31 米
- 座標格式：`(5665, 100)` 小數格式

**目標：**

- 達到 `pyexiv2` 精度：1/138,219 = 0.0000072 秒
- 實際精度：±0.0002 米
- 座標格式：`(22105589, 911470)` 分數格式

**改進方案：**

- [ ] 替換 `piexif` 為 `pyexiv2`
- [ ] 或改進 `piexif` 的精度處理，使用 `Fraction` 類別
- [ ] 實現動態分母選擇，避免精度損失

### 3. 時區處理不準確 ⚠️ 高優先級

**現況：**

- 使用簡單的經度/15 計算時區偏移
- 可能導致時間偏差

**目標：**

- 使用 `timezonefinder` 精確獲取 GPS 座標對應的時區
- 使用 `pytz` 進行準確的時區轉換

**改進方案：**

- [ ] 安裝 `timezonefinder` 和 `pytz` 依賴
- [ ] 實現基於 GPS 座標的時區推斷
- [ ] 改進時間戳處理邏輯

### 4. EXIF 標籤完整性 ⚠️ 中優先級

**現況：**

- 缺少 XMP 資料支援
- 沒有 360° 照片的特殊處理

**目標：**

- 支援 XMP 標籤（用於 360° 照片）
- 添加投影類型標記

**改進方案：**

- [ ] 添加 XMP 資料寫入功能
- [ ] 實現 360° 照片的投影類型標記
- [ ] 添加 `PictureType` 支援

### 5. 時區偏移標籤支援 ⚠️ 中優先級

**現況：**

- 嘗試添加時區偏移標籤但可能不被支援
- 時區資訊不完整

**目標：**

- 正確添加 `OffsetTimeOriginal` 標籤
- 確保時區資訊完整

**改進方案：**

- [ ] 檢查 `piexif` 對時區標籤的支援
- [ ] 實現標準的時區偏移格式
- [ ] 添加時區驗證機制

### 6. 程式架構優化 ⚠️ 低優先級

**現況：**

- 所有功能集中在一個大函數中
- 程式碼可讀性和維護性較差

**目標：**

- 模組化設計
- 分離 EXIF 處理邏輯

**改進方案：**

- [ ] 創建獨立的 EXIF 處理類別
- [ ] 分離 GPS 處理邏輯
- [ ] 重構主函數結構

### 7. 依賴管理 ⚠️ 低優先級

**現況：**

- 只使用 `piexif`
- 缺少專業的 EXIF 處理庫

**目標：**

- 添加 `pyexiv2` 支援
- 添加時區處理依賴

**改進方案：**

- [ ] 更新 `requirements.txt`
- [ ] 添加 `pyexiv2`、`timezonefinder`、`pytz`
- [ ] 實現依賴檢查機制

## 🔧 技術實現細節

### GPS 精度改進

```python
# 現況 (piexif)
gps_ifd[piexif.GPSIFD.GPSLatitude] = [(d, 1), (m, 1), (int(s*100), 100)]

# 目標 (pyexiv2 風格)
from fractions import Fraction
f = Fraction.from_float(s).limit_denominator()
num_s, denom_s = f.as_integer_ratio()
gps_ifd[piexif.GPSIFD.GPSLatitude] = [(d, 1), (m, 1), (num_s, denom_s)]
```

### 時區處理改進

```python
# 現況
tz_offset = int(longitude / 15)

# 目標
import timezonefinder
import pytz
tz_finder = timezonefinder.TimezoneFinder()
tz_name = tz_finder.timezone_at(lng=longitude, lat=latitude)
tz = pytz.timezone(tz_name)
```

## 📈 預期效果

### 精度提升

- **GPS 精度**：從 ±0.31 米 提升到 ±0.0002 米（1,550 倍提升）
- **時區準確性**：從粗略估算提升到精確計算
- **EXIF 完整性**：支援更多專業標籤

### 功能增強

- 支援 360° 照片
- 更準確的時間戳
- 更完整的元資料

## 🚀 實施順序

1. **第一階段**：相機資訊缺失問題（最高影響，低難度）
2. **第二階段**：GPS 精度改進（高影響，中等難度）
3. **第三階段**：時區處理改進（高影響，中等難度）
4. **第四階段**：EXIF 標籤完整性（中影響，低難度）
5. **第五階段**：程式架構優化（低影響，高難度）

## 📝 注意事項

- 保持向後相容性
- 確保錯誤處理機制
- 添加詳細的日誌記錄
- 測試各種邊界情況

---

**建立日期：** 2025-01-12

**最後更新：** 2025-01-12

**狀態：** 待實施

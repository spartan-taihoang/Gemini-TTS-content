# Hướng dẫn tạo artwork cho track bằng Gemini

Dùng cho MindFit (và SleepFit). Mục tiêu: mỗi track có một ảnh bìa cùng một phong cách, đọc rõ tiêu đề màu trắng
đè lên, và trông ổn ở mọi chỗ app hiển thị. Đợt 1 (xong): các track ở tab **Sleep** (stories, kids, music,
study, soundscapes), mỗi track một ảnh. Đợt 2: **daily prayer** và **meditation**, mỗi loại **một ảnh dùng chung**
cho mọi track của loại đó (mục 5b).

## 1. App hiển thị ảnh thế nào (phải biết trước khi tạo)

| Chỗ hiển thị | Kích thước | Cắt ảnh | Đè lên ảnh |
|---|---|---|---|
| Thẻ lưới ở tab Sleep (`SleepCard`) | cao 200 pt, rộng ~nửa màn hình; app tải ảnh ở **540 × 600 px** (tỉ lệ 9:10) | cắt lấp đầy (aspect fill), góc bo | **tiêu đề trắng, căn giữa, bắt đầu cách mép trên 64 pt** (khoảng 1/3 trên); **nhãn tròn tối ở đáy** (tên narrator hoặc "Piano · Ocean"); ổ khóa góc trên trái nếu premium |
| Dòng story / danh sách | vuông 64 × 64 và 112 × 112 pt | cắt vuông, góc bo 14 | không |
| Player | ảnh nhỏ vuông | cắt vuông | không |

Hệ quả:

1. **Tạo ảnh vuông 1:1**, tối thiểu **1024 × 1024 px**. Ảnh vuông cắt thành 9:10 chỉ mất một chút hai bên, và vẫn
   dùng nguyên cho các ô vuông.
2. **Chủ thể nằm trong 70% ở giữa**, không sát mép (mép bị cắt). Riêng **15% phía dưới** sẽ bị cắt hẳn khi xóa
   watermark (mục 4), nên không đặt gì quan trọng sát đáy.
3. **Vùng giữa và 1/3 trên phải tối, ít chi tiết**: tiêu đề trắng nằm ở đó. Không đặt chi tiết sáng, rối ở giữa
   ảnh. Đáy ảnh cũng nên tối vì có nhãn.
4. **Tuyệt đối không có chữ** trong ảnh (app tự viết tiêu đề). Không logo, không watermark, không chữ ký.
5. Track có sẵn **gradient màu** (`art_from` → `art_to`), hiện trong lúc ảnh đang tải. Chọn màu ảnh gần với
   gradient đó (cột "Gradient" bên dưới) để lúc ảnh hiện ra không bị "nháy" màu.

## 2. Giới hạn upload (backend)

- Định dạng: **JPEG, PNG hoặc WebP**. Tối đa **10 MB** (nên để dưới 1 MB: JPEG chất lượng ~85 là đủ).
- Không bắt buộc để publish: track không có ảnh vẫn hiện gradient.
- Một ảnh có thể dùng cho nhiều track (Vanilla Lo-Fi và Ravel Lo-Fi có 2 track mỗi bài, dùng chung ảnh).

## 3. Phong cách chung (giữ giống nhau cho mọi ảnh)

Dán **khối phong cách** này vào đầu mọi prompt, rồi thêm **mô tả chủ thể** của từng track ở mục 5.

```text
Square 1:1 cover art for a calm bedtime and relaxation app. Soft, painterly digital illustration with gentle
gradients and subtle grain, like a quiet storybook painting. Muted, dusky palette; low contrast; dreamy and warm.
Simple composition: one clear subject in the lower-middle of the frame but well above the bottom edge, with plenty of soft, dark, empty space in
the upper-middle area. Calm, peaceful mood, nothing scary or dramatic, no harsh light. The edges of the image will be
cropped, so keep the subject within the central 70 percent and leave the bottom 15 percent free of anything important. No text, no letters, no numbers, no logos, no
watermark, no signature, no border, no frame.
```

Thêm theo loại track:

| Loại | Thêm vào cuối khối phong cách |
|---|---|
| Sleep story | `Night-time scene, deep blues and indigo, soft moonlight or lamplight glow.` |
| Kids story | `Gentle children's picture-book style, rounded friendly shapes, soft warm colors, cozy and sweet, still calm.` |
| Relaxing music | `Abstract or nature-inspired, flowing soft shapes suggesting music, warm and soothing.` |
| Study music | `Cozy, softly lit desk or window scene, calm focus, warm lamp light, gentle and uncluttered.` |
| Soundscape | `Atmospheric nature scene focused on the sound source, immersive and tranquil, no people.` |

Lưu ý khi dùng Gemini:

- Model tạo ảnh của Gemini (backend đang cấu hình `gemini-2.5-flash-image`, đổi qua `GEMINI_IMAGE_MODEL`) hoặc
  Gemini app / AI Studio đều được. Nếu có chỗ chọn tỉ lệ, chọn **1:1**.
- Không mô tả người thật, nhân vật có bản quyền, hay phong cách của một họa sĩ cụ thể đang sống.
- Người trong ảnh: nhìn từ xa hoặc từ phía sau, không cận mặt (đỡ lỗi mặt và tay).
- Nếu ảnh có chữ lạ, tạo lại với câu `Absolutely no text or lettering anywhere.` ở cuối.
- Tạo 3–4 phương án mỗi track, chọn cái có vùng giữa tối và thoáng nhất.

## 4. Quy trình

1. Ghép prompt: **khối phong cách** + dòng theo **loại track** + **mô tả chủ thể** (mục 5).
2. Tạo 3–4 ảnh, chọn 1. Kiểm tra theo mục 6.
3. Lưu ảnh gốc vào `artwork/`, đặt tên theo track (ví dụ `artwork/the_night_train_north.png`).
4. Chạy **một lệnh** để cắt watermark và thu nhỏ:
   ```bash
   python3 artwork/prepare_artwork.py artwork
   ```
   Mỗi ảnh gốc thành **`<tên>_clean_small.jpg`** bên cạnh (ảnh gốc giữ nguyên), và chỉ cần file này:
   - Cắt **dấu sao lấp lánh của Gemini ở góc dưới phải**: bỏ phần dưới 100 px + 6% cạnh ảnh (~16% ở ảnh 1024 px,
     ~11% ở ảnh 2048 px), lấy hình vuông ở giữa.
   - Thu về **1024 px** (không phóng to nếu phần còn lại nhỏ hơn) và lưu **JPEG dưới 200 KB** ở chất lượng cao nhất.
   - Tùy chọn: `--side right` cắt bên phải thay vì dưới (giữ đáy ảnh); `--cut 0.18` cắt theo tỉ lệ cố định nếu dấu
     sao còn sót; `--size 800`, `--max-kb 100` để nhỏ hơn; `--out DIR` để lưu chỗ khác.
   - Chạy lại nhiều lần cũng được: script bỏ qua các file `_clean_small` đã có và ghi đè kết quả.
   Upload **`_clean_small.jpg`**, không upload ảnh gốc.
5. Gửi lại cho Claude để upload lên dev và gắn vào track (hoặc tự làm: web-admin → Tracks → mở track →
   Art image → upload). Với Vanilla Lo-Fi và Ravel Lo-Fi, gắn cùng ảnh cho cả track Relaxing và track Study.

## 5. Danh sách track cần ảnh (đợt 1: tab Sleep, 21 ảnh)

### Sleep stories

| Track | Mô tả chủ thể (dán sau khối phong cách) | Gradient |
|---|---|---|
| The Shepherd's Lantern | `An old shepherd seen from behind, sitting against a low stone wall on a hilltop at night, a small glowing lantern on a rock beside him, a few sleeping sheep, a sky full of stars.` | #3A4E7A → #0F1630 |
| The Night Train North | `An old green night train with warm glowing windows travelling through a snowy pine forest under a full moon, soft falling snow.` | #4A5D7E → #121A2B |
| The Cottage by the Tide | `A small white cottage with one lit window on the dunes beside a calm sea at dusk, the moon laying a silver path on the water.` | #7FA9B8 → #1C3440 |

### Kids stories

| Track | Mô tả chủ thể | Gradient |
|---|---|---|
| Samuel Hears a Voice | `A small boy sitting up in a simple bed inside a quiet tent, a single golden oil lamp glowing nearby, listening, seen from the side.` | #E8B07A → #5A3A6B |
| The Lost Sheep | `A kind shepherd carrying a small fluffy lamb on his shoulders across moonlit green hills, holding a lantern, seen from a distance.` | #A7C4A0 → #3E5A3A |
| The Big Red Umbrella | `A big friendly brown bear holding a large red umbrella in the rain, with a rabbit, a mouse, a hedgehog, a squirrel and a little bird huddled underneath, a forest path.` | #E07A6B → #6B2A2A |
| Kiko and the Kite | `A little girl seen from behind on a grassy hilltop, flying a handmade paper kite with a long ribbon tail high into a soft evening sky.` | #F2C46D → #4E7FA8 |

### Relaxing music

| Track | Mô tả chủ thể | Gradient |
|---|---|---|
| Quiet Keys | `Soft abstract piano keys dissolving into gentle violet waves of light.` | #8C7BB8 → #2F2650 |
| Soft Piano | `A single upright piano in a dim, warm room, a soft lamp glow, sheet music, calm and empty.` | #D9C4A8 → #4A3A2E |
| Vanilla Lo-Fi (dùng cho cả Study) | `A cozy window seat at dusk with a steaming mug, headphones and a vinyl record, warm vanilla and caramel tones.` | #E8C9A0 → #6B4A3A |
| Ravel Lo-Fi (dùng cho cả Study) | `An antique piano in a softly lit Parisian room at twilight, lavender light through tall windows.` | #B8A9D9 → #3A2F5C |

### Study music

| Track | Mô tả chủ thể | Gradient |
|---|---|---|
| Piano by the Stream | `A small wooden desk with an open notebook beside a window overlooking a quiet forest stream, morning light.` | #93BFA9 → #2C4E40 |

### Soundscapes

| Track | Mô tả chủ thể | Gradient |
|---|---|---|
| Summer Night Crickets | `Tall grass and wildflowers in a meadow on a warm summer night, fireflies glowing softly, a deep starry sky.` | #4A5A3A → #141C10 |
| Music Box Waltz | `An open antique music box with a tiny turning ballerina, glowing softly on a dark wooden shelf, gentle sparkles.` | #F2D0D9 → #5C3A4A |
| Gentle Rain | `Soft rain falling over a quiet forest at night, misty air, raindrops catching faint light.` | #7E93A8 → #1F2A36 |
| Rain on the Window | `Raindrops running down a window pane at night, the blurred warm glow of a room light behind the glass.` | #6F8BA0 → #16222E |
| Quiet Stream | `A small clear stream flowing over smooth stones in a mossy forest, soft green light.` | #7FB5A8 → #1E3F38 |
| Ocean Waves | `Slow waves rolling onto a wide empty beach at dusk, soft foam, a calm horizon.` | #5E8FB5 → #0F2238 |
| Soft Harmony | `Abstract soft glowing light ribbons floating in a deep violet space, like a calm aurora.` | #B8A0C9 → #2E2340 |

Track cũ không cần làm: Canon in D (đã có ảnh), River flows in you (track test). Hai devotional (New Every Morning,
The Good Shepherd) chưa hiện ở đâu trong iOS, để sau.

### Ambient sounds (âm nền người dùng trộn dưới bài nghe)

Rain và Ocean dùng lại ảnh của track Gentle Rain và Ocean Waves (cùng audio), không cần tạo. Chỉ còn Fireplace. Dòng
theo loại: dùng dòng của **Soundscape**.

| Ambient | Tên file | Mô tả chủ thể |
|---|---|---|
| Fireplace | `fireplace.png` | `A cozy stone fireplace with a softly glowing wood fire in a dark, quiet room, warm embers, a knitted blanket draped over an armchair nearby. No people.` |

Ảnh ambient sẽ hiện ở bộ trộn âm nền trong player (chưa build, #42), nên vẫn theo các quy tắc ở mục 1.

## 5b. Đợt 2: daily prayer và meditation (2 ảnh dùng chung)

Không làm ảnh riêng từng bài: **1 ảnh cho cả 31 daily prayer** và **1 ảnh cho cả 19 meditation**. Prayer và
meditation chỉ khác nhau ở lời, nên một ảnh chung cho mỗi loại giữ app gọn và đồng bộ; tiêu đề trên thẻ (do app viết)
đã phân biệt từng bài. Claude upload mỗi ảnh **một lần** rồi gắn cùng ảnh đó vào mọi track của loại.

Các ảnh này hiện app chưa dùng ở đâu (tab Meditation, thẻ hằng ngày ở Home chưa build; First Session, Library, Player
chưa hiện ảnh track), nhưng nên có sẵn trên dev để khi các màn đó xong là hiện luôn.

Vì một ảnh phải hợp với mọi bài, chủ thể nên **chung chung, không gắn với một câu Kinh Thánh hay một chủ đề cụ thể**:
không người, không chữ, không biểu tượng riêng của một bài.

Ghép prompt như mục 4: **khối phong cách (mục 3)** + dòng theo loại dưới đây + **mô tả chủ thể**. Tạo 3–4 phương án,
chọn 1, lưu vào `artwork/` với đúng tên file rồi chạy `prepare_artwork.py` như thường lệ.

| Loại (số track) | Tên file | Dòng theo loại (thêm sau khối phong cách) | Mô tả chủ thể |
|---|---|---|---|
| Daily prayer (31) | `daily_prayer.png` | `Quiet, reverent evening mood, warm candlelight against deep blue dusk, gentle and hopeful.` | `A small wooden table by an open window at dusk, a single lit candle and an open old book resting beside it, soft curtains moving in the breeze, a few stars appearing in the deep blue sky outside. No people, no hands.` |
| Meditation (19) | `meditation.png` | `Serene, spacious and still, soft mist and gentle light, a feeling of slow breathing.` | `A perfectly still lake at twilight surrounded by soft misty hills, a single small tree on the shore reflected in the water, the last warm glow of the sun on the horizon and the first stars above. No people.` |

Gợi ý cho từng loại:

- **Daily prayer**: tông ấm (nến, ánh hoàng hôn) trên nền xanh đậm, giống cảm giác cầu nguyện buổi tối. Không vẽ tay
  chắp hay người quỳ: dễ lỗi và làm ảnh bị gắn với một hình ảnh cụ thể. Nếu ảnh có chữ trên trang sách, thêm
  `The book's pages are blank, no writing.` và tạo lại.
- **Meditation**: tông lạnh, rộng, tĩnh (mặt hồ, sương, trời chạng vạng). Vùng trời phía trên phải tối và trống để đọc
  tiêu đề. Không có hoa sen, tư thế ngồi thiền hay biểu tượng tôn giáo khác (app là app Kitô giáo).

Màu gradient: 31 prayer đang có 6 gradient khác nhau và 19 meditation có 5 gradient theo bộ sưu tập (hiện lúc ảnh
đang tải). Khi ảnh chung đã lên, Claude có thể đổi gradient của mọi bài trong loại thành 2 màu chính của ảnh để lúc
tải không bị đổi màu; nói với Claude nếu muốn.

## 6. Kiểm tra trước khi upload

- [ ] Ảnh vuông, ≥ 1024 px, JPEG/PNG/WebP, dưới 10 MB.
- [ ] Không có chữ, số, logo; đã chạy `prepare_artwork.py` và dấu sao Gemini đã mất (upload file `_clean_small.jpg`).
- [ ] Vùng giữa và 1/3 trên đủ tối để chữ trắng đọc rõ (thử đặt chữ trắng to lên ảnh).
- [ ] Chủ thể nằm trong 70% giữa, không bị cắt khi thành 9:10 hay hình vuông nhỏ.
- [ ] Màu chủ đạo gần với gradient của track.
- [ ] Cùng phong cách với các ảnh đã làm (đặt cạnh nhau xem có đồng bộ không).
- [ ] Không có người thật, nhân vật có bản quyền, mặt hay tay bị méo.

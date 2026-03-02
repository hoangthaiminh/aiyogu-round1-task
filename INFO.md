# 📘 Báo cáo Dự án
## Homework Helper & Auto-feedback
**Hệ thống nộp bài và phản hồi tự động bằng AI (vai: giáo viên chấm bài Việt Nam)**

---

### I. Tên đề tài
**Homework Helper & Auto-feedback — Hệ thống hỗ trợ nộp bài, chấm và phản hồi tự động bằng trí tuệ nhân tạo**

---

### II. Lĩnh vực
Ứng dụng công nghệ thông tin trong giáo dục — Hỗ trợ dạy và học bằng AI

---

### III. Thực hiện
- Nhóm tác giả: ___Chicken Team___  
- Lớp/Khóa: ___TK6___  
- Công cụ sử dụng: Kết hợp 2 công cụ __ChatGPT__(Để viết Prompt) và __Claude__(Để tạo dự án)

---

### IV. Lý do chọn đề tài (Nêu vấn đề, nguyên nhân, hậu quả)
**Nêu vấn đề:**  
Trong môi trường học phổ thông, học sinh thường thiếu phản hồi kịp thời, cụ thể về các bài tập tự luận, bài toán và bài lập trình. Giáo viên do phải quản lý nhiều học sinh nên không thể chấm kỹ từng bài, dẫn đến học sinh không biết mình sai ở đâu và cách cải thiện ra sao.

**Nguyên nhân:**  
- Sự giới hạn về thời gian và nguồn lực của giáo viên;  
- Quy trình chấm thủ công tốn thời gian;  
- Thiếu công cụ hỗ trợ đánh giá, phân tích lỗi và gợi ý sửa lỗi tự động.

**Hậu quả:**  
- Học sinh lặp lại lỗi, tiến bộ chậm;  
- Giảm hiệu quả học tập cá nhân;  
- Giáo viên chịu áp lực công việc lớn.

---

### V. Mục tiêu của dự án
Xây dựng một hệ thống web nhẹ (Flask + SQLite) giúp:
- Học sinh nộp bài trực tuyến và nhận **phản hồi chi tiết, mang tính giáo dục** ngay sau khi nộp;  
- Hệ thống đóng vai trò là trợ lý chấm (AI đóng vai giáo viên Việt Nam) để phát hiện lỗi, sửa, đưa ra gợi ý và điểm tham khảo;  
- Lưu trữ lịch sử nộp và phản hồi để theo dõi quá trình tiến bộ.

---

### VI. Giải pháp (Tóm tắt)
Sử dụng mô hình AI (OpenAI/Gemini hoặc tương tự) gọi từ server để phân tích bài làm học sinh. Hệ thống nhận đầu vào là văn bản hoặc ảnh (kết hợp OCR nếu là ảnh), gửi prompt theo vai trò "giáo viên chấm bài Việt Nam", nhận về cấu trúc phản hồi chuẩn hoá (summary, corrections, suggestions, score, rubric, các kiểm tra đặc thù cho toán/code) rồi lưu và hiển thị cho học sinh.

---

### VII. Dự án đã có các tính năng (Mô tả chức năng ngoài, dễ hiểu cho người không chuyên)
> Mục này trình bày các chức năng chính của hệ thống bằng ngôn ngữ đơn giản, nhằm giúp ban giám khảo, giáo viên, và học sinh hình dung rõ ràng những gì hệ thống làm được.

1. **Đăng ký & Đăng nhập người dùng**  
   - Cho phép học sinh, giáo viên (admin) tạo tài khoản, đăng nhập và bảo vệ thông tin cá nhân.

2. **Nộp bài trực tiếp bằng văn bản**  
   - Học sinh có thể dán trực tiếp nội dung bài làm vào form để nộp, phù hợp với bài văn, bài luận, câu trả lời tự luận.

3. **Nộp ảnh bài làm (hỗ trợ OCR)**  
   - Học sinh có thể chụp ảnh bài viết tay hoặc file in rồi upload; hệ thống chuyển ảnh sang văn bản bằng OCR để AI phân tích.

4. **Phân tích & Nhận xét tự động bằng AI (vai giáo viên Việt Nam)**  
   - AI đọc bài làm, tóm tắt nội dung chính và nhận diện các vấn đề:
     - Lỗi ngữ pháp, chính tả, diễn đạt (bài văn/tiếng Anh).  
     - Bước sai, logic không chính xác (bài toán).  
     - Lỗi cú pháp/logic (bài code).
   - AI đưa ra nhận xét mang tính giáo dục, lịch sự, và cụ thể.

5. **Sửa lỗi mẫu & Checklist chấm**  
   - Hệ thống hiển thị các câu/đoạn gốc kèm với phiên bản đã sửa và giải thích ngắn gọn cho mỗi sửa.  
   - Cung cấp checklist tiêu chí chấm (rubric) kèm điểm tham khảo.

6. **Điểm tham khảo & Phân mục tiêu chí (Rubric)**  
   - AI chấm điểm tham khảo (0–10) và phân chia điểm theo các tiêu chí: nội dung, cấu trúc, ngôn ngữ, tính sáng tạo.

7. **Lịch sử nộp & Phiên bản phản hồi**  
   - Mỗi lần nộp được lưu; học sinh có thể xem các phiên bản trước và tiến trình cải thiện theo thời gian.

8. **Yêu cầu chấm lại (Re-evaluate)**  
   - Học sinh có thể chỉnh sửa theo gợi ý và gửi yêu cầu chấm lại để nhận phản hồi cập nhật.

9. **Bảng tổng quan cho giáo viên / admin (tuỳ chọn)**  
   - Giáo viên xem danh sách bài nộp, duyệt hoặc chỉnh sửa phản hồi AI trước khi công bố chính thức.

10. **Xuất báo cáo (CSV/PDF)**  
    - Giáo viên có thể tải báo cáo tổng hợp điểm hoặc lịch sử nộp để lưu trữ, in ấn, hoặc dùng cho đánh giá học sinh.

11. **Chế độ demo (Mock feedback)**  
    - Khi chưa cấu hình API key, hệ thống chạy chế độ demo bằng feedback mẫu để kiểm tra giao diện và luồng hoạt động.

---

### VIII. Ý nghĩa và tác động dự kiến
- **Hỗ trợ học sinh** nhận phản hồi nhanh, cụ thể để sửa lỗi và tiến bộ ngay lập tức; đặc biệt hữu ích cho những em cần ôn luyện tự học.  
- **Hỗ trợ giáo viên** giảm bớt khối lượng chấm bài ban đầu, giúp dành thời gian cho các công việc cần chuyên môn hơn (giảng dạy, hướng dẫn cá nhân).  
- **Khuyến khích học tập chủ động**: học sinh có thể nộp nhiều lần, theo dõi tiến bộ theo lịch sử phản hồi.

---

### IX. Hạn chế hiện tại
- Phản hồi AI là **tham khảo**, không thay thế hoàn toàn chấm tay của giáo viên.  
- Độ chính xác OCR phụ thuộc chất lượng ảnh.  
- Hiệu quả phụ thuộc vào chất lượng mô hình AI và prompt; cần tinh chỉnh để phù hợp ngữ cảnh giáo dục Việt Nam.

---

### X. Hướng phát triển (gợi ý)
- Thêm module giảng dạy nhỏ (micro-lessons) dựa trên lỗi phổ biến.  
- Tích hợp hàng loạt lớp (classroom mode) cho giáo viên quản lý lớp.  
- Thêm phân tích thống kê toàn lớp, biểu đồ tiến bộ.  
- Bổ sung human-in-the-loop: giáo viên kiểm duyệt feedback AI trước khi công bố.

---

### XI. Kết luận ngắn
Dự án là một công cụ hỗ trợ thực tiễn, gọn nhẹ, giúp kết hợp AI vào việc học và chấm bài ở bậc phổ thông. Mục tiêu chính là **tăng tốc độ và chất lượng phản hồi**, giúp học sinh tiến bộ nhanh hơn và giảm thiểu gánh nặng cho giáo viên.

---

*Document này được ChatGPT tạo ra*
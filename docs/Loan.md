# **V. RAG VÀ CHAT AI**

## **1\. Giới thiệu RAG trong hệ thống**

### **1.1. Bối cảnh và động lực nghiên cứu**

#### **1.1.1. Hiện tượng hallucination trong các hệ thống LLM chuyên ngành**

Trong thập kỷ gần đây, các mô hình ngôn ngữ lớn như GPT, Gemini và LLaMA đã mang lại bước đột phá đáng kể trong lĩnh vực xử lý ngôn ngữ tự nhiên. Tuy nhiên, khi triển khai các chatbot sử dụng LLM trong các hệ thống nghiệp vụ chuyên ngành \- đặc biệt là lĩnh vực tài chính và tín dụng \- người phát triển phải đối mặt với một vấn đề nghiêm trọng: hiện tượng ảo giác (hallucination).

Hallucination xảy ra khi LLM tự tạo ra thông tin không có trong dữ liệu huấn luyện, hoặc đưa ra các câu trả lời lỗi thời do kiến thức bị đóng băng tại thời điểm huấn luyện. Đây là hạn chế cố hữu của kiến trúc transformer thuần túy, xuất phát từ cơ chế bộ nhớ tham số \- tức là toàn bộ kiến thức của mô hình được mã hóa trong các trọng số được tối ưu hóa trong quá trình huấn luyện, mà không có cơ chế tra cứu tài liệu bên ngoài trong thời gian thực.

Trong bối cảnh tư vấn tín dụng, hallucination có thể dẫn tới những hệ quả nghiêm trọng về mặt nghiệp vụ và pháp lý, bao gồm: đưa ra thông tin sai về chính sách phê duyệt khoản vay; cung cấp số liệu tỷ lệ nợ trên thu nhập hoặc xác suất vỡ nợ sai lệch so với kết quả thực tế từ mô hình học máy; và nguy cơ rò rỉ thông tin nội bộ hoặc dữ liệu cá nhân của khách hàng.

#### **1.1.2. Giải pháp: Kiến trúc RAG trong CreditIntel**

Để giải quyết các vấn đề trên, nhóm phát triển CreditIntel đã lựa chọn kiến trúc RAG \- một phương pháp kết hợp khả năng tìm kiếm tài liệu với khả năng sinh văn bản của LLM, từ đó đảm bảo câu trả lời luôn có cơ sở trích dẫn từ nguồn tri thức đáng tin cậy. Đặc biệt, hệ thống RAG của CreditIntel được thiết kế với nguyên tắc "có trích dẫn nguồn, không bịa thông tin" \- mọi câu trả lời đều phải dựa trên tài liệu chính sách, dữ liệu hồ sơ thực, hoặc kết quả học máy đã được tính toán sẵn.

Mục tiêu cụ thể của hệ thống RAG trong CreditIntel được thể hiện qua bảng sau:

| Mục tiêu | Mô tả chi tiết |
| ----- | ----- |
| Giải thích kết quả học máy cá nhân hóa | Trả lời câu hỏi như "Tại sao tôi bị đánh giá rủi ro CAO?" dựa trên dữ liệu hồ sơ thực của khách hàng |
| Tư vấn tài chính cơ bản | Hướng dẫn khách hàng về DTI, điểm tín dụng, khả năng vay và các chỉ số tài chính liên quan |
| Giải thích chính sách | Trả lời về tiêu chí phê duyệt, quy trình auto-reject, yêu cầu hồ sơ và các quy định hiện hành |
| Hỗ trợ điều chỉnh đơn vay | Đề xuất phương án vay phù hợp hơn khi đơn bị từ chối tự động, tối ưu hóa cấu trúc đơn vay |

### **1.2. Phạm vi báo cáo**

Báo cáo này tập trung phân tích module backend/rag/ trong hệ thống CreditIntel, bao gồm 17 file Python và 2 file Markdown tri thức chuyên ngành. Cấu trúc và quy mô của các thành phần được trình bày trong bảng dưới đây:

| Thành phần | Số file | Tổng kích thước |
| ----- | ----- | ----- |
| Module RAG core (backend/rag/) | 17 file .py | \~102 KB |
| Knowledge Base (backend/rag/knowledge/) | 2 file .md | \~36 KB |
| Tích hợp (chat\_service.py, loan\_adjustment\_tool.py) | 2 file .py | Phụ thuộc vào kiến trúc tổng thể |

Ngoài ra, báo cáo còn tham chiếu tới các tài liệu thiết kế trong docs/rag/ (3 file, khoảng 58 KB) và docs/superpowers/specs/ (12 file thiết kế kỹ thuật cho các iteration phát triển RAG). Các công nghệ cốt lõi được sử dụng trong hệ thống:

| Công nghệ | Phiên bản / Model | Vai trò trong hệ thống |
| ----- | ----- | ----- |
| LangChain | \>= 0.3.0 | Framework xây dựng RAG pipeline theo chuẩn LCEL |
| Qdrant | Local Docker server | Vector database lưu trữ và tìm kiếm embedding |
| OpenRouter | API Gateway | Truy cập Gemini 2.5 Flash và OpenAI text-embedding-3-small |
| FastEmbed | Local inference | BM25 sparse embedding và Cross-Encoder reranker |
| PostgreSQL | Supabase | Lưu chat history, session, user context, ML results |

### **1.3. Đóng góp chính của hệ thống**

Hệ thống RAG trong CreditIntel đóng góp các thiết kế kỹ thuật nổi bật sau đây, mỗi đặc điểm phản ánh một quyết định thiết kế có chủ ý nhằm đáp ứng các yêu cầu đặc thù của lĩnh vực tín dụng tài chính:

#### **1.3.1. Pipeline RAG đa giai đoạn 6 bước**

Pipeline được thiết kế theo chuỗi tuần tự: Input Guardrail \- Intent Router \- Query Rewriting \- Hybrid Search \- Reranking \- Personalization \- LLM Generation \- Output Guardrail. Mỗi bước đều có cơ chế xuống cấp tự nhiên riêng, đảm bảo hệ thống không bị lỗi khi một thành phần gặp sự cố. Thiết kế này cho phép mỗi module được phát triển, kiểm thử và bảo trì độc lập.

#### **1.3.2. Hybrid Search kết hợp Dense và Sparse BM25**

Hệ thống tận dụng đồng thời khả năng hiểu ngữ nghĩa (tìm kiếm theo ngữ nghĩa qua vector dày đặc 1536 chiều) và khả năng khớp từ khóa chính xác (qua BM25 vector thưa). Sự kết hợp này đặc biệt hiệu quả với thuật ngữ chuyên ngành tín dụng như DTI, FICO, CIC \- những thuật ngữ mà vector dày đặc đơn thuần có thể không nắm bắt chính xác do tần suất xuất hiện thấp trong dữ liệu huấn luyện tổng quát.

#### **1.3.3. Cross-Encoder Reranking đa ngôn ngữ**

Sử dụng mô hình jinaai/jina-reranker-v2-base-multilingual (khoảng 1,1 GB) chạy hoàn toàn trên máy chủ cục bộ để tái xếp hạng kết quả tìm kiếm. Cross-Encoder đánh giá độ liên quan bằng cách xử lý cặp câu hỏi và đoạn văn cùng lúc qua một transformer duy nhất, cho phép cơ chế attention hoạt động giữa hai chuỗi, từ đó đạt độ chính xác cao hơn đáng kể so với bi-encoder đơn thuần.

#### **1.3.4. Parent-Child Chunking cho tài liệu Markdown**

Phân đoạn tài liệu thành cấu trúc phân cấp hai tầng: tìm kiếm ở mức chi tiết (child chunk, tối đa 700 ký tự) nhưng trả kết quả ở mức ngữ cảnh rộng (parent section, tối đa 3500 ký tự). Chiến lược này giải quyết một mâu thuẫn cơ bản trong RAG: chunk nhỏ giúp truy xuất chính xác hơn, nhưng chunk lớn cung cấp đủ ngữ cảnh cho LLM để sinh câu trả lời chất lượng cao.

#### **1.3.5. Cá nhân hóa giọng điệu đa chiều**

Hệ thống hỗ trợ 7 trạng thái đơn vay kết hợp với 6 loại ý định, tạo ra tổng cộng 42 tổ hợp phản hồi được điều chỉnh riêng. Mỗi khách hàng nhận câu trả lời với giọng điệu phù hợp với trạng thái tâm lý và nhu cầu thông tin cụ thể, thay vì nhận một phản hồi chung chung. Đây là điểm khác biệt quan trọng so với các hệ thống chatbot tài chính thông thường.

#### **1.3.6. Bảo mật đa lớp**

Hệ thống triển khai 20 mẫu nhận diện prompt injection và 11 mẫu nhận diện PII probing ở đầu vào; đồng thời sử dụng 14 mẫu nhận diện rò rỉ thông tin nội bộ và 6 mẫu nhận diện cam kết phê duyệt sai ở đầu ra. Cơ chế bảo mật hai lớp là cần thiết để đảm bảo tuân thủ các quy định bảo vệ dữ liệu trong lĩnh vực tài chính.

## **2\. Cơ sở lý thuyết**

## **2.1. Retrieval-Augmented Generation (RAG)**

#### **2.1.1. Định nghĩa và lịch sử phát triển**

Retrieval-Augmented Generation (RAG) là kiến trúc kết hợp hai thành phần cốt lõi: một hệ thống tìm kiếm thông tin để truy xuất các đoạn tài liệu liên quan từ kho tri thức, và một mô hình ngôn ngữ lớn để sinh câu trả lời dựa trên thông tin đã truy xuất. Khái niệm RAG được đề xuất lần đầu bởi Lewis et al. (2020) trong bài báo "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" tại hội nghị NeurIPS, như một giải pháp cho bài toán tạo sinh văn bản đòi hỏi kiến thức chuyên sâu.

Ý tưởng trung tâm của RAG là: thay vì bắt LLM phải ghi nhớ toàn bộ kiến thức trong trọng số mô hình, ta bổ sung cho nó một bộ nhớ ngoài dưới dạng kho tài liệu có thể tìm kiếm. Khi nhận câu hỏi, hệ thống sẽ trải qua ba giai đoạn chính: lập chỉ mục tài liệu, truy xuất tài liệu liên quan và sinh câu trả lời từ tài liệu đã truy xuất.

#### **2.1.2. Ba giai đoạn của RAG Pipeline**

##### **2.1.2.1. Giai đoạn lập chỉ mục**

Trong giai đoạn này, tài liệu nguồn được xử lý thành các đoạn văn bản nhỏ. Mỗi đoạn sau đó được chuyển đổi thành vector embedding thông qua một mô hình encoder, và vector được lưu trữ vào cơ sở dữ liệu vector cùng với siêu dữ liệu nguồn gốc, vị trí, nội dung gốc. Chất lượng của quá trình lập chỉ mục \- đặc biệt là chiến lược phân đoạn và lựa chọn mô hình embedding \- ảnh hưởng trực tiếp tới chất lượng của toàn bộ hệ thống.

##### **2.1.2.2. Giai đoạn truy xuất**

Khi nhận câu hỏi từ người dùng, hệ thống mã hóa câu hỏi thành vector sử dụng cùng mô hình embedding. Sau đó, hệ thống tìm kiếm trong cơ sở dữ liệu vector các đoạn có vector gần nhất với vector của câu hỏi theo độ đo khoảng cách xác định, thường là Cosine Similarity hoặc Dot Product. Các đoạn có độ tương đồng cao nhất được chọn làm ngữ cảnh cho giai đoạn sinh văn bản.

##### **2.1.2.3. Giai đoạn sinh văn bản**

Các đoạn tài liệu đã truy xuất được ghép vào prompt cùng với câu hỏi gốc và các hướng dẫn hệ thống, sau đó được gửi cho LLM để sinh câu trả lời. LLM được yêu cầu chỉ sử dụng thông tin từ ngữ cảnh được cung cấp và không suy diễn ngoài phạm vi tài liệu. Câu trả lời cuối cùng thường đi kèm với trích dẫn nguồn để người dùng có thể xác minh tính chính xác.

#### **2.1.3. So sánh RAG với Chatbot thuần LLM**

Để làm rõ lý do lựa chọn kiến trúc RAG cho CreditIntel, bảng dưới đây trình bày so sánh toàn diện giữa hai phương pháp:

| Tiêu chí | Chatbot thuần LLM | Chatbot RAG |
| ----- | ----- | ----- |
| Nguồn kiến thức | Chỉ bộ nhớ tham số từ huấn luyện | Bộ nhớ tham số kết hợp tài liệu truy xuất |
| Hallucination | Cao \- LLM tự suy diễn khi không biết | Thấp \- trả lời dựa trên tài liệu truy xuất được kiểm chứng |
| Cập nhật kiến thức | Phải fine-tune hoặc huấn luyện lại toàn bộ | Chỉ cần cập nhật kho tài liệu, không đụng đến model |
| Trích dẫn nguồn | Không thể \- không có nguồn gốc rõ ràng | Có thể \- siêu dữ liệu từ đoạn gốc đi kèm câu trả lời |
| Chi phí vận hành | Thấp \- chỉ 1 lần gọi LLM | Cao hơn \- embedding \+ tìm kiếm \+ gọi LLM |
| Độ trễ phản hồi | Thấp (\~1-5 giây) | Cao hơn (\~3-15 giây, tùy reranking) |

Trong ngữ cảnh CreditIntel \- nơi chính sách tín dụng thay đổi theo thời gian, dữ liệu khách hàng là thời gian thực, và sai sót có thể dẫn tới hậu quả pháp lý \- RAG là lựa chọn phù hợp hơn so với chatbot thuần LLM dù chi phí vận hành cao hơn.

### **2.2. Vector Embedding và Tìm kiếm ngữ nghĩa**

#### **2.2.1. Dense Embedding**

Dense embedding là phương pháp biểu diễn văn bản dưới dạng vector số thực dày đặc trong không gian nhiều chiều, sao cho các văn bản có ý nghĩa tương đồng sẽ có vector gần nhau trong không gian đó. Mỗi chiều trong không gian embedding biểu diễn một đặc trưng ngữ nghĩa trừu tượng được mô hình học được trong quá trình huấn luyện.

Trong CreditIntel, mô hình embedding được sử dụng là openai/text-embedding-3-small với 1536 chiều, truy cập qua OpenRouter API. Dense embedding có ưu điểm nổi bật là khả năng hiểu ngữ nghĩa \- nó có thể tìm được các đoạn văn có ý nghĩa tương tự dù dùng từ khác nhau. Ví dụ, câu hỏi "Tại sao đơn của tôi bị từ chối?" có thể tìm thấy đoạn tài liệu nói về "Tiêu chí auto-reject" mặc dù không chia sẻ từ khóa chung.

#### **2.2.2. Sparse Embedding \- BM25**

BM25 là thuật toán tìm kiếm từ khóa cổ điển thuộc họ TF-IDF, được sử dụng rộng rãi trong các hệ thống tìm kiếm thông tin truyền thống từ những năm 1990\. Khác với dense embedding, BM25 tạo ra vector thưa \- vector với phần lớn phần tử bằng 0, chỉ các vị trí tương ứng với từ xuất hiện trong văn bản mới có giá trị khác 0\.

Điểm BM25 cho tài liệu với truy vấn được tính theo công thức có xét đến tần suất xuất hiện của từ, độ hiếm của từ trong toàn bộ kho ngữ liệu, và đặc điểm độ dài tài liệu. Trong CreditIntel, BM25 được triển khai qua thư viện FastEmbedSparse với model Qdrant/bm25, chạy hoàn toàn trên máy chủ cục bộ không cần gọi API bên ngoài. BM25 đặc biệt hữu ích cho các thuật ngữ chuyên ngành tín dụng như DTI, FICO, CIC, auto-reject \- những thuật ngữ mà dense embedding có thể không nắm bắt chính xác do ít xuất hiện trong dữ liệu huấn luyện tổng quát.

#### **2.2.3. Cosine Similarity**

Cosine Similarity là phương pháp đo độ tương đồng giữa hai vector bằng cách tính cosine của góc giữa chúng. Giá trị kết quả nằm trong khoảng từ \-1 đến 1, với 1 nghĩa là hoàn toàn tương đồng về hướng và \-1 là hoàn toàn đối ngược. Ưu điểm của Cosine Similarity so với Euclidean Distance là không bị ảnh hưởng bởi độ lớn của vector, chỉ phụ thuộc vào hướng \- điều này phù hợp với văn bản vì một đoạn văn dài hơn không nhất thiết khác về ngữ nghĩa so với đoạn văn ngắn hơn cùng chủ đề.

Trong CreditIntel, Qdrant được cấu hình sử dụng Cosine distance cho tìm kiếm vector dày đặc, với collection creditintel-kb chứa các vector 1536 chiều tương ứng với các child chunk của tài liệu tri thức.

### **2.3. Hybrid Search \- Tìm kiếm hỗn hợp**

#### **2.3.1. Động lực và ưu điểm kết hợp**

Cả dense embedding và sparse BM25 đều có điểm mạnh và hạn chế riêng biệt khi áp dụng trong thực tế. Hybrid Search ra đời để tận dụng điểm mạnh của cả hai phương pháp, bù đắp lẫn nhau một cách có hệ thống:

| Phương pháp | Điểm mạnh | Hạn chế |
| ----- | ----- | ----- |
| Dense Search | Hiểu ngữ nghĩa sâu, tìm được paraphrase và các diễn đạt tương đương | Yếu với thuật ngữ chuyên ngành hiếm gặp, ký hiệu viết tắt |
| Sparse BM25 | Khớp từ khóa chính xác, nhanh, không cần GPU | Không hiểu ngữ nghĩa, bỏ lỡ các paraphrase và diễn đạt khác biệt |
| Hybrid Search | Tận dụng điểm mạnh của cả hai: vừa hiểu ngữ nghĩa vừa khớp từ khóa | Phức tạp hơn về triển khai, cần cơ chế kết hợp điểm số |

Minh họa cụ thể trong CreditIntel: khi xử lý câu hỏi "Mức DTI bao nhiêu là an toàn?", dense search tìm được các đoạn về "tỷ lệ nợ trên thu nhập" và "gánh nặng tài chính" (khớp ngữ nghĩa), trong khi BM25 tìm chính xác các đoạn chứa keyword "DTI" (khớp từ khóa). Kết hợp cả hai đảm bảo không bỏ sót bất kỳ tài liệu liên quan nào.

#### **2.3.2. Reciprocal Rank Fusion (RRF)**

Khi kết hợp kết quả từ dense search và sparse BM25, hệ thống cần một cơ chế hợp nhất điểm số từ hai phương pháp có thang đo khác nhau. Qdrant sử dụng Reciprocal Rank Fusion \- một thuật toán kết hợp dựa trên thứ hạng thay vì điểm số thô. RRF có ưu điểm là ổn định hơn và không bị ảnh hưởng bởi sự khác biệt về thang đo điểm số giữa các phương pháp khác nhau.

#### **2.3.3. Triển khai trong CreditIntel**

Qdrant hỗ trợ hybrid search thông qua RetrievalMode.HYBRID, cho phép thực hiện đồng thời cả dense và sparse search trong một truy vấn duy nhất. Trong file retriever.py, vectorstore được cấu hình với embedding dày đặc OpenAIEmbeddings 1536 chiều và sparse embedding BM25, với chế độ RetrievalMode.HYBRID. Kết quả hybrid search được Qdrant kết hợp nội bộ bằng RRF, trả về top-K ứng viên tốt nhất từ cả hai phương pháp, sau đó được đưa vào bước Reranking.

### **2.4. Cross-Encoder Reranking \- Tái xếp hạng**

#### **2.4.1. Bi-Encoder so với Cross-Encoder**

Trong kiến trúc RAG hiện đại, bước Reranking đóng vai trò quan trọng trong việc cải thiện chất lượng kết quả truy xuất. Có hai kiến trúc chính để đánh giá mức độ liên quan giữa câu hỏi và tài liệu:

Bi-Encoder được sử dụng ở bước truy xuất: mã hóa câu hỏi và tài liệu độc lập thành 2 vector riêng biệt, sau đó so sánh bằng cosine similarity. Ưu điểm là nhanh vì vector tài liệu có thể được tính trước và lưu vào chỉ mục. Tuy nhiên, nhược điểm là kém chính xác do không có tương tác trực tiếp giữa câu hỏi và tài liệu trong quá trình mã hóa.

Cross-Encoder được sử dụng ở bước tái xếp hạng: ghép câu hỏi và tài liệu thành một chuỗi duy nhất và đưa qua transformer. Mô hình nhìn thấy cả câu hỏi và tài liệu cùng lúc, cho phép cơ chế self-attention hoạt động giữa tất cả các token của cả hai chuỗi. Điều này dẫn đến độ chính xác cao hơn đáng kể, nhưng chậm hơn vì phải mã hóa lại cho mỗi cặp câu hỏi \- tài liệu.

Chiến lược tối ưu là sử dụng Bi-Encoder để lọc nhanh top-K ứng viên từ toàn bộ kho ngữ liệu, sau đó dùng Cross-Encoder để tái xếp hạng chính xác trong tập K ứng viên đó. Đây chính xác là kiến trúc được triển khai trong CreditIntel.

#### **2.4.2. Triển khai Cross-Encoder trong CreditIntel**

CreditIntel sử dụng mô hình jinaai/jina-reranker-v2-base-multilingual (kích thước khoảng 1,1 GB), hỗ trợ đa ngôn ngữ bao gồm tiếng Việt \- một yêu cầu quan trọng vì người dùng CreditIntel tương tác bằng tiếng Việt. Model được tải về máy chủ cục bộ thông qua thư viện fastembed và chạy hoàn toàn trên CPU, không cần GPU.

Reranker được thiết kế theo mô hình Singleton với tải lười (Lazy Loading) trong file reranker.py. Model chỉ được tải vào bộ nhớ khi có request đầu tiên yêu cầu reranking, nhưng để tránh độ trễ 30-40 giây ở request đầu tiên do phải tải model từ đĩa, server thực hiện khởi động trước khi chạy thông qua sự kiện startup trong main.py.

#### **2.4.3. Quy trình Reranking ba bước**

Sau khi Hybrid Search trả về 20 child chunks ứng viên, Cross-Encoder Reranker thực hiện: tính điểm liên quan cho 20 cặp câu hỏi \- chunk bằng cách cho mỗi cặp qua transformer cross-encoder; sắp xếp lại 20 chunks theo điểm số giảm dần; chọn top-12 chunks sau reranking. Kết quả sau đó đi qua bước mở rộng tài liệu parent để truy ngược từ child chunk lên parent section tương ứng, cuối cùng còn lại top-4 parent sections được đưa vào prompt LLM.

### **2.5. Chunking Strategies \- Chiến lược phân đoạn tài liệu**

#### **2.5.1. Tổng quan các phương pháp chunking**

Chunking là quá trình chia tài liệu gốc thành các đoạn nhỏ hơn trước khi mã hóa thành vector. Chất lượng chunking ảnh hưởng trực tiếp tới chất lượng truy xuất và cuối cùng là chất lượng câu trả lời. Đây là một trong những quyết định thiết kế quan trọng nhất trong hệ thống RAG thực tế:

| Phương pháp | Mô tả | Ưu điểm | Nhược điểm |
| ----- | ----- | ----- | ----- |
| Fixed-size | Chia cố định theo số ký tự hoặc token | Đơn giản, chunk đều đặn, dễ kiểm soát | Có thể cắt ngang ý nghĩa câu/đoạn văn |
| Recursive | Chia theo separator thứ tự ưu tiên | Giữ cấu trúc câu và đoạn văn tự nhiên | Chunk không đều, khó kiểm soát kích thước |
| Semantic | Chia theo độ tương đồng ngữ nghĩa giữa các câu liền kề | Giữ ngữ nghĩa tốt nhất, chunk liên kết chặt | Tốn chi phí embedding cao, chậm |
| Parent-Child (Chọn) | Chia 2 tầng: Parent ngữ cảnh rộng và Child chi tiết | Kết hợp ưu điểm: tìm chi tiết nhưng trả ngữ cảnh đầy đủ | Phức tạp hơn trong triển khai và quản lý siêu dữ liệu |

#### **2.5.2. Parent-Child Chunking \- Phương pháp được chọn trong CreditIntel**

CreditIntel triển khai chiến lược Parent-Child Chunking \- một phương pháp phân đoạn phân cấp giải quyết một mâu thuẫn cơ bản trong thiết kế RAG: chunk nhỏ giúp truy xuất chính xác hơn vì vector embedding tập trung vào một ý cụ thể, nhưng chunk lớn cung cấp đủ ngữ cảnh cho LLM để hiểu và trả lời chính xác.

Giải pháp là tách biệt hai chức năng: sử dụng child chunk nhỏ tối đa 700 ký tự cho bước tìm kiếm vector, nhưng khi trả kết quả cho LLM thì truy ngược lên parent section lớn hơn tối đa 3500 ký tự để cung cấp đủ ngữ cảnh. Mối quan hệ Parent-Child được duy trì qua siêu dữ liệu gắn kèm mỗi child chunk, bao gồm parent\_id và parent\_content, cho phép hệ thống tự động truy ngược từ child lên parent trong thời gian thực.

Cấu hình cụ thể trong file chunking.py: PARENT\_MAX\_CHARS \= 3500 (kích thước tối đa mỗi parent section), CHILD\_MAX\_CHARS \= 700 (kích thước tối đa mỗi child chunk), và CHILD\_OVERLAP\_CHARS \= 80 (overlap giữa các child chunk liên tiếp để đảm bảo không mất thông tin tại ranh giới chunk).

#### **2.5.3. Xử lý đặc thù Markdown và sinh ID ổn định**

Tài liệu tri thức trong CreditIntel được viết dưới định dạng Markdown, với cấu trúc phân cấp rõ ràng theo heading. Thuật toán chunking trong CreditIntel được thiết kế theo kiểu nhận biết Markdown, nghĩa là nhận biết và tôn trọng cấu trúc heading khi phân chia parent section \- mỗi parent section tương ứng với một section trong tài liệu Markdown, không bị cắt ngang giữa các heading.

Một đặc điểm liên quan là sinh parent\_id ổn định: mỗi parent section nhận một ID ổn định (SHA-1 theo nội dung) dùng để gom nhóm các child về đúng parent ở runtime. Cần lưu ý rằng parent\_id này không phải là point ID của Qdrant: nhánh ingest mặc định gọi store.add\_documents(chunks) mà không truyền point ID nên Qdrant tự sinh UUID ngẫu nhiên, do đó chạy lại ingest có thể nhân bản điểm dữ liệu. Cách an toàn để nạp lại sau khi sửa tài liệu là dùng \--recreate.

### **2.6. Quản lý bộ nhớ trong RAG hội thoại**

#### **2.6.1. Sliding Window Memory**

Trong bối cảnh chatbot hội thoại, LLM cần có ngữ cảnh của lịch sử hội thoại để trả lời câu hỏi tiếp theo chính xác. Tuy nhiên, cửa sổ ngữ cảnh của LLM là có giới hạn và chi phí tỷ lệ với số token, nên không thể đưa toàn bộ lịch sử hội thoại vào mỗi request. CreditIntel giải quyết vấn đề này bằng cơ chế cửa sổ trượt với ngân sách 2000 token.

Cơ chế hoạt động: hệ thống tải các tin nhắn gần nhất từ PostgreSQL theo thứ tự mới nhất trước, tích lũy cho đến khi tổng số token vượt quá ngân sách 2000\. Các tin nhắn vừa vặn trong ngân sách được đưa vào prompt dưới dạng lịch sử hội thoại, trong khi các tin nhắn cũ hơn được bao phủ bởi bản tóm tắt.

#### **2.6.2. Lazy Summarization**

Khi số lượng tin nhắn nằm ngoài cửa sổ trượt đạt tới ngưỡng tối thiểu (từ 6 tin nhắn trở lên), hệ thống tự động kích hoạt quá trình tóm tắt lười (lazy summarization). LLM được gọi riêng để sinh bản tóm tắt với tham số temperature=0,2 và giới hạn max\_tokens=500. Bản tóm tắt này được lưu vào bảng chat\_sessions trong PostgreSQL và được tái sử dụng cho các request tiếp theo, tránh sinh lại trong mỗi lượt hội thoại.

## **3\. Kiến trúc tổng quan**

### **3.1. Sơ đồ kiến trúc hệ thống**

![][image1]

Hệ thống RAG của CreditIntel được thiết kế theo kiến trúc pipeline đa giai đoạn, tích hợp chặt chẽ với tầng dịch vụ chat và tầng lưu trữ kép gồm Qdrant Vector DB và PostgreSQL. Toàn bộ luồng xử lý từ khi khách hàng gửi tin nhắn cho tới khi nhận phản hồi trải qua các bước chính được mô tả dưới đây.

Luồng xử lý bắt đầu từ câu hỏi của khách hàng gửi qua FastAPI, qua kiểm tra giới hạn tốc độ (20 tin nhắn/phút/người dùng), lưu tin nhắn vào PostgreSQL, tải ngữ cảnh bộ nhớ, và kiểm tra trạng thái máy trạng thái điều chỉnh khoản vay. Sau đó, câu hỏi đi vào RAG Pipeline 6 bước. Cuối cùng, phản hồi được trả về kèm theo nguồn trích dẫn và mã phiên.

### **3.2. Các thành phần chính của Pipeline RAG**

Hệ thống RAG được tổ chức thành các module riêng biệt, mỗi module đảm nhận một chức năng cụ thể trong pipeline. Nguyên tắc trách nhiệm đơn được áp dụng nghiêm ngặt \- mỗi file Python chỉ chịu trách nhiệm cho một khía cạnh của pipeline:

| Thành phần | File nguồn | Vai trò | KT |
| ----- | ----- | ----- | ----- |
| Orchestrator | chain.py | Điều phối toàn bộ pipeline 6 bước; quản lý LangChain LCEL chain | 7,4 KB |
| Ingest Pipeline | ingest.py | Nạp tài liệu từ knowledge/ vào Qdrant; hỗ trợ CLI với \--dry-run và \--recreate | 4,3 KB |
| Chunking Engine | chunking.py | Thuật toán Parent-Child phân đoạn nhận biết Markdown; làm giàu siêu dữ liệu; sinh ID ổn định | 10,2 KB |
| Retriever | retriever.py | Hybrid Search \- Reranking \- mở rộng Parent-Child; Singleton | 4,7 KB |
| Reranker | reranker.py | Cross-Encoder scoring; Singleton \+ Lazy Loading; fallback khi model chưa sẵn sàng | 1,8 KB |
| Intent Router | router.py | Phân loại ý định: Regex fast-path \+ LLM JSON fallback, 6 loại intent | 7,9 KB |
| Query Rewriter | query\_rewriter.py | Viết lại câu hỏi ngữ cảnh thành truy vấn độc lập cho retrieval (tối đa 500 ký tự) | 4,4 KB |
| Guardrails | guardrails.py | Bảo mật đầu vào (injection, PII) và đầu ra (rò rỉ nội bộ, cam kết sai) | 8,4 KB |
| Personalizer | personalizer.py | Ánh xạ 7 trạng thái đơn vay sang tông giọng LLM; 6 loại intent instructions | 9,2 KB |
| Memory Manager | memory.py | Cửa sổ trượt (ngân sách 2000 token) \+ tóm tắt lười khi từ 6 tin nhắn trở lên | 6,4 KB |
| Context Builder | context\_builder.py | Xây dựng 4 khối ngữ cảnh người dùng từ PostgreSQL | 16,0 KB |
| Prompt Template | prompts.py | ChatPromptTemplate 8 biến: system (6 placeholder) \+ chat\_history \+ question | 3,5 KB |
| Exception Hierarchy | exceptions.py | Cây exception: RAGError \- RetrievalError, LLMError, RAGTimeoutError | 0,5 KB |
| Package Facade | \_\_init\_\_.py | Facade tải lười \- export 15 hàm API cho các module bên ngoài | 1,3 KB |
| Eval Runner | eval\_runner.py | Bộ kiểm thử tự động offline cho RAG pipeline | 6,1 KB |
| Eval Metrics | eval\_metrics.py | Định nghĩa chỉ số: Faithfulness, Context Precision, Overall | 12,5 KB |

#### **3.2.1. Mô hình Lazy-Loading Facade**

Module rag/ sử dụng mô hình Lazy-Loading Facade thông qua cơ chế \_\_getattr\_\_ của Python \- các sub-module chỉ được import khi có code bên ngoài thực sự gọi tới. Thiết kế này mang lại hai lợi ích quan trọng: thứ nhất, giảm thời gian khởi động của server vì không cần tải toàn bộ RAG module khi boot; thứ hai, tách biệt phụ thuộc \- module nào import lỗi chỉ ảnh hưởng khi thực sự gọi tới module đó, không làm crash toàn bộ server.

Facade export tổng cộng 15 hàm API bao gồm các hàm cốt lõi như invoke (thực thi toàn bộ RAG pipeline), build\_user\_context (xây dựng ngữ cảnh người dùng), classify\_intent (phân loại ý định), và check\_input (kiểm tra guardrail đầu vào). Mỗi hàm được lưu vào bộ nhớ đệm sau lần import đầu tiên để tránh chi phí cho các lần gọi tiếp theo.

### **3.3. Ngăn xếp công nghệ chi tiết**

#### **3.3.1. Qdrant \- Vector Database**

Qdrant đóng vai trò trung tâm của hệ thống truy xuất, chịu trách nhiệm lưu trữ và tìm kiếm cả vector dày đặc và vector thưa. Trong môi trường phát triển, Qdrant chạy dưới dạng Docker container cục bộ tại http://localhost:6333, cho phép phát triển và kiểm thử hoàn toàn ngoại tuyến mà không cần phụ thuộc vào dịch vụ đám mây.

| Thuộc tính cấu hình | Chi tiết |
| ----- | ----- |
| Collection name | creditintel-kb |
| Vector dày đặc | 1536 chiều, Cosine distance, model text-embedding-3-small |
| Vector thưa | Tham số BM25 sparse, model Qdrant/bm25 |
| Chế độ tìm kiếm | RetrievalMode.HYBRID (Dense \+ Sparse đồng thời, RRF fusion) |
| Triển khai | Docker container cục bộ \- đường nâng cấp sang Qdrant Cloud khi mở rộng |

Qdrant được lựa chọn vì khả năng chạy hoàn toàn cục bộ không cần API key đám mây, hỗ trợ hybrid search tích hợp sẵn, API đơn giản qua Python client, và có lộ trình nâng cấp rõ ràng lên cloud khi mở rộng quy mô mà không cần thay đổi code.

#### **3.3.2. LangChain LCEL \- Framework RAG**

LangChain được sử dụng theo mô hình LCEL, trong đó pipeline được biểu diễn dưới dạng chuỗi pipe. Ba thành phần trong pipeline LCEL của CreditIntel bao gồm: ChatPromptTemplate với 8 biến đầu vào: trong system prompt có 6 placeholder (tên khách hàng, hướng dẫn cá nhân hóa, hướng dẫn theo ý định, hồ sơ người dùng, tóm tắt hội thoại, tài liệu truy xuất), cộng với lịch sử hội thoại (chat\_history) và câu hỏi hiện tại; ChatOpenAI kết nối tới Gemini 2.5 Flash qua OpenRouter với temperature=0,3 để cân bằng giữa chính xác và tự nhiên; và StrOutputParser() để chuyển đổi output từ LLM sang chuỗi text thuần.

LangChain LCEL mang lại ba lợi ích quan trọng cho hệ thống: tính kết hợp linh hoạt cho phép dễ thêm, bớt hoặc thay thế bất kỳ thành phần nào mà không ảnh hưởng các thành phần khác; kiểm tra kiểu dữ liệu mỗi bước nhận và trả về kiểu xác định được kiểm tra tại thời điểm biên dịch; và hỗ trợ streaming cho phép xuất dữ liệu theo từng token dù CreditIntel chưa kích hoạt tính năng này trong phiên bản hiện tại.

#### **3.3.3. OpenRouter \- Cổng API đa model**

OpenRouter hoạt động như cổng API đa model \- chỉ cần một API key duy nhất để truy cập nhiều model từ nhiều nhà cung cấp khác nhau. CreditIntel sử dụng OpenRouter qua endpoint tương thích OpenAI SDK, cho phép tận dụng trực tiếp ChatOpenAI và OpenAIEmbeddings từ LangChain mà không cần viết adapter riêng.

| Dịch vụ | Model | Tham số đặc thù |
| ----- | ----- | ----- |
| LLM Generation | google/gemini-2.5-flash | temperature=0,3; timeout=30s; max\_retries=2 |
| LLM Intent Router | google/gemini-2.5-flash | temperature=0,0; max\_tokens=60; timeout=30s |
| LLM Query Rewriter | google/gemini-2.5-flash | temperature=0,0; timeout=30s |
| LLM Summarizer | google/gemini-2.5-flash | temperature=0,2; max\_tokens=500; timeout=30s |
| Dense Embedding | openai/text-embedding-3-small | 1536 chiều; timeout=10s; max\_retries=2 |

#### **3.3.4. FastEmbed \- Công cụ inference cục bộ**

FastEmbed là thư viện inference chạy hoàn toàn cục bộ không cần gọi API bên ngoài, cung cấp hai khả năng quan trọng trong hệ thống CreditIntel. Thứ nhất, sparse embedding BM25 qua FastEmbedSparse với model Qdrant/bm25, tính toán vector thưa trực tiếp trên CPU cho hybrid search. Thứ hai, Cross-Encoder Reranking qua TextCrossEncoder với model jinaai/jina-reranker-v2-base-multilingual khoảng 1,1 GB, thực hiện chấm điểm liên quan cho 20 cặp câu hỏi \- chunk ở bước reranking.

Việc sử dụng FastEmbed cho hai chức năng này mang lại lợi ích về chi phí và độ trễ, đặc biệt quan trọng cho cross-encoder reranking vốn đòi hỏi nhiều lần inference. Tuy nhiên, cần lưu ý rằng model reranker khoảng 1,1 GB cần được quản lý cẩn thận về bộ nhớ trong môi trường vận hành.

#### **3.3.5. PostgreSQL \- Cơ sở dữ liệu quan hệ**

PostgreSQL đóng vai trò lưu trữ bền vững cho tất cả dữ liệu phi-vector trong hệ thống CreditIntel. Dữ liệu cá nhân của khách hàng không được nhúng vào Qdrant để tránh rò rỉ giữa các khách hàng, mà luôn được truy vấn trực tiếp từ PostgreSQL theo user\_id từ JWT tại thời điểm mỗi request.

| Bảng | Vai trò trong RAG |
| ----- | ----- |
| users | Thông tin khách hàng \- được sử dụng trong bước cá nhân hóa |
| loan\_applications | Đơn vay và kết quả học máy (xác suất vỡ nợ, mức rủi ro, hạn mức đề xuất) \- Context Builder 4 khối |
| chat\_sessions | Siêu dữ liệu phiên chat (tiêu đề, bản tóm tắt) \- Memory Manager |
| chat\_messages | Lịch sử tin nhắn (vai trò, nội dung, nguồn, cờ lỗi) \- Cửa sổ trượt và tóm tắt |

### **3.4. Luồng dữ liệu tổng quan**

#### **3.4.1. Luồng xử lý đầy đủ từ câu hỏi đến phản hồi**

Toàn bộ luồng xử lý trong hệ thống RAG CreditIntel có thể được tóm tắt theo 14 bước tuần tự sau:

Bước 1 \- Nhận request: Khách hàng gửi POST /chat với message và session\_id. FastAPI chuyển tiếp sang chat\_service.send(). Bước 2 \- Giới hạn tốc độ và lưu tin: Kiểm tra tần suất gửi tin (20 tin nhắn/phút/người dùng) trong PostgreSQL. Nếu vượt ngưỡng, trả về HTTP 429\. Nếu hợp lệ, lưu tin nhắn người dùng vào chat\_messages trước khi gọi RAG. Bước 3 \- Tải bộ nhớ: memory.py tải tin nhắn gần nhất từ PostgreSQL và tóm tắt lịch sử nếu cần. Bước 4 \- Máy trạng thái điều chỉnh đơn vay: Kiểm tra xem người dùng có đang trong luồng điều chỉnh đơn vay hay không.

Bước 5 \- Xây dựng ngữ cảnh người dùng: context\_builder.py truy vấn loan\_applications để xây dựng ngữ cảnh 4 khối. Bước 6 \- Gọi RAG Pipeline: chain.py khởi động pipeline 6 bước. Bước 7 \- Input Guardrail: Kiểm tra 20 mẫu injection và 11 mẫu PII probing. Từ chối ngay nếu phát hiện nguy cơ. Bước 8 \- Phân loại ý định: router.py phân loại ý định qua Regex fast-path, nếu không khớp thì dùng LLM JSON fallback. Bước 9 \- Viết lại câu hỏi: query\_rewriter.py viết lại câu hỏi thành truy vấn độc lập, không phụ thuộc ngữ cảnh hội thoại.

Bước 10 \- Hybrid Retrieval và Reranking: retriever.py thực hiện Hybrid Search \- Cross-Encoder Rerank \- mở rộng Parent, trả về top-4 parent sections. Bước 11 \- Cá nhân hóa: personalizer.py xác định tông giọng phù hợp dựa trên trạng thái đơn vay và intent. Bước 12 \- Sinh văn bản LLM: LCEL chain sinh câu trả lời từ prompt đầy đủ. Bước 13 \- Output Guardrail: Kiểm tra 14 mẫu rò rỉ và 6 mẫu cam kết sai. Bước 14 \- Lưu và trả về: Lưu tin nhắn trợ lý vào PostgreSQL và trả về phản hồi kèm nguồn và mã phiên.

#### **3.4.2. Cơ chế lưu nguyên tử và chịu lỗi**

Một đặc điểm quan trọng trong thiết kế của CreditIntel là cơ chế lưu nguyên tử: tin nhắn người dùng được commit vào PostgreSQL trước khi gọi RAG pipeline. Điều này đảm bảo không bao giờ mất tin nhắn của khách hàng \- ngay cả khi RAG pipeline bị lỗi hoàn toàn, tin nhắn người dùng vẫn được lưu an toàn.

Khi xảy ra lỗi RAGError, chat\_service lưu một tin nhắn trợ lý đặc biệt với cờ lỗi vào PostgreSQL, sau đó trả về HTTP 503 cho client. Người dùng nhận được thông báo lỗi thân thiện thay vì màn hình trắng, và lịch sử hội thoại vẫn được bảo toàn đầy đủ cho phiên tiếp theo.

### **3.5. Cấu hình môi trường RAG**

Toàn bộ cấu hình RAG được quản lý tập trung qua file backend/.env và load vào ứng dụng thông qua core/config.py và rag/config.py. Nguyên tắc quản lý cấu hình tập trung giúp dễ dàng điều chỉnh hành vi hệ thống mà không cần sửa code:

| Biến môi trường | Giá trị mặc định | Mô tả |
| ----- | ----- | ----- |
| RAG\_LLM\_MODEL | google/gemini-2.5-flash | Model LLM chính cho Generation, Routing, Rewriting, Summarization |
| RAG\_EMBEDDING\_MODEL | openai/text-embedding-3-small | Model Dense Embedding (1536 chiều) |
| RAG\_BM25\_MODEL | Qdrant/bm25 | Model Sparse Embedding \- chạy cục bộ |
| RAG\_RERANKER\_ENABLED | True | Bật/tắt Cross-Encoder Reranking |
| RAG\_RERANKER\_MODEL | jinaai/jina-reranker-v2-base-multilingual | Model Cross-Encoder (\~1,1 GB, cục bộ) |
| RAG\_RERANKER\_CANDIDATE\_K | 20 | Số child chunks trước reranking |
| RAG\_RERANKER\_TOP\_K | 12 | Số child chunks sau reranking |
| RAG\_TOP\_K | 4 | Số parent sections cuối cùng gửi vào LLM |
| RAG\_LLM\_TIMEOUT\_SECONDS | 30 | Timeout cho mỗi lần gọi LLM API |
| RAG\_LLM\_MAX\_RETRIES | 2 | Số lần thử lại khi gọi LLM thất bại |
| RAG\_MEMORY\_WINDOW\_TOKEN\_BUDGET | 2000 | Ngân sách token cho cửa sổ trượt |
| RAG\_MEMORY\_MIN\_MESSAGES\_TO\_SUMMARIZE | 6 | Ngưỡng tin nhắn ngoài cửa sổ để kích hoạt tóm tắt |
| RAG\_MEMORY\_SUMMARY\_MAX\_TOKENS | 500 | Giới hạn token cho output tóm tắt |

### **3.6. Cây phân cấp Exception**

Hệ thống RAG định nghĩa cây exception riêng trong exceptions.py, tách biệt hoàn toàn khỏi exception của ứng dụng chính. Cây exception có cấu trúc: RAGError là lớp cơ sở, phân nhánh thành RetrievalError khi lỗi Qdrant hoặc dịch vụ Embedding, LLMError khi lỗi OpenRouter hoặc gọi LLM, và RAGTimeoutError khi cuộc gọi vượt quá ngân sách timeout.

Nguyên tắc xử lý exception phản ánh mức độ quan trọng của từng thành phần trong pipeline. RetrievalError và RAGTimeoutError ở bước truy xuất được xử lý theo cơ chế xuống cấp tự nhiên \- ghi log cảnh báo và tiếp tục với documents \= \[\] để LLM vẫn có thể trả lời dựa trên ngữ cảnh người dùng. Ngược lại, LLMError và RAGTimeoutError ở bước sinh văn bản được đẩy lên chat\_service và trả về HTTP 503, vì không có LLM thì không thể sinh câu trả lời.

| Exception | Hành vi xử lý | Lý do thiết kế |
| ----- | ----- | ----- |
| RetrievalError | Ghi log \+ tiếp tục với documents \= \[\] | Xuống cấp tự nhiên \- LLM vẫn trả lời được từ ngữ cảnh người dùng |
| RAGTimeoutError (truy xuất) | Ghi log cảnh báo \+ tiếp tục với documents \= \[\] | Tương tự RetrievalError \- truy xuất là tùy chọn |
| LLMError | Đẩy lên chat\_service \- HTTP 503 | Không có LLM thì không thể sinh câu trả lời cho người dùng |
| RAGTimeoutError (sinh văn bản) | Đẩy lên chat\_service \- HTTP 503 | Tương tự LLMError \- sinh văn bản là bắt buộc |
| RAGError (chat\_service) | Lưu tin nhắn lỗi \- HTTP 503 | Bảo toàn lịch sử, thông báo lỗi thân thiện cho người dùng |

### **3.7. Cấu trúc thư mục**

Hệ thống RAG được tổ chức trong thư mục backend/rag/ với cấu trúc phẳng \- tất cả các module nằm cùng cấp trong một thư mục duy nhất, thay vì chia thành các sub-package. Quyết định thiết kế này giúp đơn giản hóa đường dẫn import và giảm độ phức tạp khi các module phụ thuộc lẫn nhau.

| File | Mô tả chức năng |
| ----- | ----- |
| \_\_init\_\_.py | Facade tải lười \- export 15 hàm API cho các module bên ngoài |
| config.py | Trung tâm cấu hình: tên model, API key, giá trị top-K, timeout |
| chain.py | Orchestrator: pipeline 6 bước từ input guardrail đến output guardrail |
| ingest.py | Pipeline nạp tài liệu: CLI với \--dry-run, \--recreate; chế độ mặc định thêm vào collection (chưa idempotent) |
| chunking.py | Parent-Child chunking: nhận biết Markdown, sinh ID ổn định, làm giàu siêu dữ liệu |
| context\_builder.py | 4 khối ngữ cảnh người dùng: Form \+ ML \+ Advisory \+ Data Quality |
| router.py | Phân loại ý định: Regex fast-path \+ LLM JSON fallback, 6 loại intent |
| query\_rewriter.py | Viết lại câu hỏi ngữ cảnh thành truy vấn độc lập (tối đa 500 ký tự) |
| retriever.py | Hybrid Search \- Cross-Encoder Rerank \- mở rộng tài liệu Parent; Singleton |
| reranker.py | Cross-Encoder: Singleton \+ Lazy Load \+ khởi động trước \+ fallback |
| guardrails.py | Đầu vào: 20 mẫu injection \+ 11 mẫu PII; Đầu ra: 14 mẫu rò rỉ \+ 6 mẫu cam kết sai |
| personalizer.py | 7 trạng thái đơn vay sang tông giọng LLM; 6 loại intent sang hướng dẫn cụ thể |
| memory.py | Cửa sổ trượt (ngân sách 2000 token) \+ tóm tắt lười (từ 6 tin nhắn ngoài cửa sổ) |
| prompts.py | ChatPromptTemplate: system prompt 9 quy tắc \+ 8 biến đầu vào (6 trong system \+ chat\_history \+ question) |
| exceptions.py | RAGError \- RetrievalError, LLMError, RAGTimeoutError |
| eval\_runner.py | Bộ kiểm thử tự động ngoại tuyến cho toàn bộ RAG pipeline |
| eval\_metrics.py | Định nghĩa chỉ số đánh giá: Faithfulness, Context Precision, Overall |
| knowledge/faq.md | \~19 KB \- 30 cặp Q\&A, 9 chủ đề về tín dụng và dịch vụ CreditIntel |
| knowledge/policy.md | \~17 KB \- 12 chương chính sách tín dụng đầy đủ |

## **4\. Giai đoạn Ingest \- Nạp và Phân Mảnh Tài Liệu**

Giai đoạn Ingest là bước nền tảng của hệ thống RAG, chịu trách nhiệm chuyển đổi tài liệu tri thức dạng Markdown thành cấu trúc dữ liệu phân cấp Parent-Child, mã hóa thành vector embedding, và lưu trữ vào Qdrant. Điểm đặc trưng quan trọng của giai đoạn này là tính tách biệt hoàn toàn với luồng xử lý câu hỏi thời gian thực: quá trình Ingest chỉ cần thực hiện một lần khi khởi tạo hệ thống hoặc cập nhật knowledge base, không ảnh hưởng đến hiệu năng phục vụ người dùng.

### **4.1. Nguồn Dữ Liệu Đầu Vào**

Hệ thống nạp tài liệu từ hai thư mục nguồn cố định: backend/rag/knowledge/ chứa FAQ và chính sách tín dụng, và docs/data\_dictionary/ chứa mô tả các trường dữ liệu của mô hình học máy. LangChain DirectoryLoader thực hiện quét đệ quy tất cả file có định dạng .md, đọc mỗi file thành một đối tượng Document gồm nội dung văn bản và siêu dữ liệu nguồn gốc.

#### **4.1.1. Knowledge Base Chính**

| File | Kích thước | Nội dung | Cấu trúc |
| ----- | ----- | ----- | ----- |
| faq.md | \~19 KB, 303 dòng | 30 cặp câu hỏi và giải đáp | 9 nhóm chủ đề (A-I): Mô hình AI, AUTO\_REJECTED, Hạn mức vay, Yếu tố tài chính, Đề xuất thay thế, Vòng đời đơn, Bổ sung thông tin, Chatbot, Bảo mật |
| policy.md | \~17 KB, 294 dòng | 12 chương chính sách tín dụng | Từ giới thiệu, phạm vi khoản vay, tiêu chí rủi ro, đến quy trình duyệt và pháp lý |

### **4.2. Thuật Toán Parent-Child Chunking**

Phân đoạn tài liệu là bài toán trọng tâm trong bất kỳ hệ thống RAG nào. Kích thước chunk ảnh hưởng trực tiếp đến chất lượng truy xuất: chunk quá nhỏ thì thiếu ngữ cảnh; chunk quá lớn thì làm loãng tín hiệu tìm kiếm. CreditIntel giải quyết bài toán này bằng chiến lược Parent-Child Chunking \- một mô hình phân cấp hai tầng được thiết kế đặc thù cho tài liệu có cấu trúc Markdown chuẩn hóa.

#### **4.2.1. Lựa Chọn Chiến Lược Chunking**

| Phương pháp | Ưu điểm | Hạn chế | Phù hợp khi |
| ----- | ----- | ----- | ----- |
| Fixed-size chunking | Đơn giản, dễ triển khai | Cắt ngang ý nghĩa, mất ngữ cảnh ở biên | Tài liệu đồng nhất, không có cấu trúc rõ ràng |
| Recursive Text Splitting | Linh hoạt, thử chia theo nhiều separator | Không hiểu cấu trúc Markdown, có thể cắt giữa Q\&A | Tài liệu đa dạng format |
| Semantic Chunking | Chia theo ngữ nghĩa thực sự | Tốn chi phí embedding khi ingest, chậm | Tài liệu dài, không có cấu trúc rõ |
| Parent-Child Chunking (Chọn) | Tìm ở mức chi tiết, trả về ngữ cảnh rộng | Phức tạp hơn, cần thiết kế siêu dữ liệu | Tài liệu có cấu trúc Markdown rõ ràng |

Lý do lựa chọn Parent-Child Chunking: CreditIntel chọn phương pháp này vì knowledge base có cấu trúc Markdown chuẩn \- FAQ dùng pattern \*\*Q: ...\*\*, Policy dùng heading \#\#. Thuật toán tận dụng cấu trúc sẵn có thay vì gọi embedding (tiết kiệm chi phí API), đồng thời đảm bảo LLM luôn nhận được ngữ cảnh trọn vẹn ở mức parent section.

#### **4.2.2. Quy Trình 5 Bước**

Bước 1 \- Đọc tài liệu: DirectoryLoader quét đệ quy tất cả file .md, tạo đối tượng Document cho mỗi file.

Bước 2 \- Gắn siêu dữ liệu: Mỗi document được bổ sung 4 trường siêu dữ liệu quan trọng:

| Trường | Giá trị ví dụ | Vai trò |
| ----- | ----- | ----- |
| source | "faq.md" | Trích dẫn nguồn trong câu trả lời |
| source\_type | "faq"/"policy" /"data\_dictionary" | Quyết định chiến lược chia ở Bước 3 |
| document\_title | "Câu Hỏi Thường Gặp (FAQ) \- CreditIntel" | Trích xuất tự động từ heading đầu tiên |
| source\_path | Đường dẫn đầy đủ | Debug và truy vết |

Bước 3 \- Parent Splitting (chia thành Parent Section): Đây là bước quan trọng nhất. Thuật toán phân biệt hai chiến lược tùy theo loại tài liệu.

Với policy.md và data dictionary: Chia theo heading Markdown \#\#. Regex tìm tất cả heading cấp 2, mỗi đoạn từ heading này đến heading tiếp theo trở thành 1 parent section. Kết quả: khoảng 13 parent sections gồm 12 chương và 1 phần mở đầu.

Với faq.md: Chia theo pattern FAQ \*\*Q: ...\*\*. Regex nhận diện mỗi cặp Q\&A, với tiêu đề section chính là nội dung câu hỏi. Kết quả: khoảng 31 parent sections gồm 30 Q\&A và 1 phần mở đầu.

Lý do thiết kế hai chiến lược tách biệt: nếu dùng chung cách chia theo heading \#\#, file FAQ sẽ bị gom thành 9 section lớn theo nhóm A-I, mỗi section chứa 3-8 cặp Q\&A. Điều này khiến truy xuất phải trả về cả nhóm khi chỉ cần 1 câu hỏi, làm loãng ngữ cảnh cho LLM. Bằng cách chia riêng theo pattern Q\&A, mỗi cặp trở thành đơn vị độc lập \- tăng độ chính xác truy xuất đáng kể.

Bước 4 \- Child Splitting (chia Parent thành Child Chunk): Mỗi parent section được chia tiếp thành các child chunks \- đây là đơn vị thực sự được mã hóa thành vector và lưu vào Qdrant:

| Tham số | Giá trị | Lý do chọn |
| ----- | ----- | ----- |
| CHILD\_MAX\_CHARS | 700 ký tự | Đủ nhỏ để embedding chính xác, đủ lớn để giữ ngữ nghĩa trọn vẹn |
| CHILD\_OVERLAP\_CHARS | 80 ký tự | Đảm bảo liên tục ngữ cảnh ở biên giữa 2 chunk liền kề |

Thuật toán sử dụng gói khối: văn bản Markdown được tách thành các khối theo dấu ngắt đoạn, sau đó gom các khối liền kề vào chunk cho đến khi vượt ngưỡng 700 ký tự. Khi tạo chunk mới, 80 ký tự cuối của chunk trước được mang sang làm phần đầu \- đảm bảo không mất thông tin ở biên. Cơ chế overlap này giải quyết vấn đề mất ngữ nghĩa tại ranh giới chunk, đặc biệt quan trọng khi câu hỏi liên quan đến nội dung trải dài qua hai đoạn liên tiếp.

Bước 5 \- Sinh parent\_id ổn định: Mỗi parent section được gán một ID ổn định dựa trên SHA-1 hash của tổ hợp source, tiêu đề section, chỉ số và 200 ký tự đầu nội dung, cắt lấy 16 ký tự hex. Cùng một tài liệu đầu vào luôn sinh ra cùng parent\_id, dùng để gom nhóm các child về đúng parent ở bước mở rộng Parent (Mục 5.4.4). Lưu ý: parent\_id KHÔNG được dùng làm point ID của Qdrant \- nhánh ingest mặc định gọi store.add\_documents(chunks) không truyền ID nên Qdrant tự sinh UUID ngẫu nhiên; do đó chạy lại ingest có thể nhân bản điểm dữ liệu, và cách nạp lại an toàn sau khi sửa tài liệu là dùng \--recreate.

#### **4.2.3. Siêu dữ liệu Gắn Kèm Mỗi Child Chunk**

Sau 5 bước, mỗi child chunk được lưu vào Qdrant kèm siêu dữ liệu đầy đủ, phục vụ cho bước mở rộng Parent và trích dẫn nguồn ở giai đoạn vận hành:

| Trường | Giá trị ví dụ | Vai trò |
| ----- | ----- | ----- |
| source | "policy.md" | Trích dẫn nguồn cho LLM |
| section\_title | "Tiêu Chí Phân Loại Rủi Ro" | Trích dẫn section cụ thể |
| parent\_id | "a3f8b2c1e9d04567" | Ánh xạ ngược child lên parent (dùng ở bước mở rộng Parent) |
| parent\_content | Nội dung parent đầy đủ | Trả về cho LLM thay vì child (ngữ cảnh rộng hơn) |
| chunk\_index | 1 | Vị trí child trong parent |
| retrieval\_unit | "child" | Phân biệt child và parent |

Trường parent\_content là thiết kế then chốt: khi truy xuất tìm được child chunk, hệ thống không sử dụng nội dung child mà lấy parent\_content trong siêu dữ liệu để gửi cho LLM \- đảm bảo LLM nhận được đoạn tài liệu trọn vẹn ý nghĩa, không bị cắt ngang. Đây là hiện thực hóa nguyên tắc cốt lõi của Parent-Child Chunking: tìm ở mức chi tiết, trả về ở mức trọn vẹn.

### **4.3. Lưu Trữ vào Qdrant**

Mỗi child chunk được mã hóa thành hai loại vector và lưu đồng thời vào Qdrant collection. Chiến lược hai vector này là nền tảng cho Hybrid Search ở giai đoạn vận hành:

| Loại vector | Model | Chiều | Vai trò |
| ----- | ----- | ----- | ----- |
| Vector dày đặc | text-embedding-3-small (OpenAI qua OpenRouter) | 1536 | Tìm kiếm ngữ nghĩa \- hiểu nghĩa câu hỏi dù dùng từ khác |
| Vector thưa | Qdrant/bm25 (FastEmbed cục bộ) | Thưa | Tìm kiếm từ khóa chính xác \- khớp thuật ngữ chuyên ngành |

Kết hợp hai loại vector là thiết kế có chủ đích: vector dày đặc giỏi hiểu paraphrase như "Tỷ lệ nợ trên thu nhập" tương đương "DTI", nhưng có thể bỏ sót từ khóa chính xác. Vector thưa BM25 ngược lại \- khớp chính xác từ khóa nhưng không hiểu đồng nghĩa. Kết hợp cả hai bao phủ được cả hai trường hợp, đặc biệt quan trọng trong lĩnh vực tín dụng với nhiều thuật ngữ viết tắt như DTI, FICO, CIC.

### **4.4. Công Cụ CLI và Các Chế Độ Chạy**

Module ingest.py cung cấp 3 chế độ chạy qua CLI, cho phép kiểm soát linh hoạt quá trình nạp dữ liệu:

| Chế độ | Lệnh | Hành vi | An toàn |
| ----- | ----- | ----- | ----- |
| Dry Run | python \-m rag.ingest \--dry-run | Chỉ liệt kê tài liệu và số chunk, không ghi dữ liệu | Hoàn toàn an toàn |
| Mặc định (append) | python \-m rag.ingest | Giữ collection cũ, thêm toàn bộ chunk (chưa idempotent \- chạy lại có thể nhân bản) | Giữ data cũ |
| Recreate | python \-m rag.ingest \--recreate | XÓA collection cũ, tạo lại từ đầu | Cần thận trọng |

Chế độ Dry Run đóng vai trò kiểm tra trước khi tốn chi phí embedding API \- đặc biệt hữu ích khi chỉnh sửa tài liệu nguồn hoặc thay đổi tham số chunking. Chỉ khi kết quả Dry Run đúng kỳ vọng, kỹ sư mới chạy chế độ mặc định hoặc Recreate để cập nhật cơ sở dữ liệu vector thực tế.

## **5\. Giai đoạn Runtime \- Pipeline Xử Lý Câu Hỏi**

Mỗi câu hỏi của khách hàng được xử lý theo pipeline đa giai đoạn 6 bước, điều phối bởi hai tầng: tầng tiền xử lý (chat\_service.py) và tầng RAG core (chain.py). Thiết kế pipeline tuần tự cho phép dừng sớm tại bất kỳ bước nào \- tiết kiệm tài nguyên khi không cần thiết và đảm bảo phản hồi nhanh cho các loại câu hỏi không cần truy xuất.

### **5.1. Tiền Xử Lý tại chat\_service.py**

Trước khi vào pipeline RAG 6 bước, chat\_service.py thực hiện 5 bước tiền xử lý quan trọng:

Giới hạn tốc độ: Đếm số tin nhắn trong 1 phút gần nhất qua bảng chat\_messages. Ngưỡng 20 tin nhắn/phút/người dùng \- vượt ngưỡng trả HTTP 429\. Đây là biện pháp chống lạm dụng API đơn giản nhưng hiệu quả, tránh tốn chi phí LLM cho các cuộc tấn công tự động.

Lưu nguyên tử \- Ghi Trước, Xử Lý Sau: Tin nhắn người dùng được lưu vào PostgreSQL trước khi gọi RAG pipeline. Thiết kế này đảm bảo không mất tin nhắn ngay cả khi RAG pipeline bị lỗi giữa chừng. Nếu LLM timeout hoặc xảy ra exception, hệ thống vẫn lưu được phản hồi lỗi HTTP 503 kèm cờ lỗi \- tạo nhật ký kiểm toán đầy đủ thay vì mất dấu vết.

Tải bộ nhớ: Module memory.py tải MemoryContext gồm hai thành phần: cửa sổ trượt gồm các tin nhắn gần nhất trong ngân sách 2000 token, và bản tóm tắt lười là tóm tắt LLM cho các tin nhắn cũ khi từ 6 tin nhắn ngoài cửa sổ chưa được tóm tắt.

Xây dựng ngữ cảnh \- 4 Khối Thông Tin Cá Nhân: Module này truy vấn bảng loan\_applications để xây dựng 4 khối thông tin inject vào prompt:

| Block | Nội dung | Nguồn |
| ----- | ----- | ----- |
| Form Context | Số tiền, kỳ hạn, DTI, credit score, việc làm, CIC | loan\_applications |
| ML Context | Xác suất vỡ nợ, mức rủi ro, hạn mức đề xuất | Kết quả dự đoán học máy |
| Advisory Context | So sánh vay và đề xuất, yếu tố rủi ro và tích cực, khuyến nghị | Tính toán từ Form và ML |
| Data Quality | Danh sách feature bị impute, mức tin cậy | Siêu dữ liệu của ML pipeline |

Lý do không nhúng thông tin cá nhân vào Qdrant: thông tin đơn vay thay đổi liên tục theo mỗi lần nộp đơn mới hoặc mỗi lần Admin duyệt. Nếu nhúng vào Qdrant sẽ phải nạp lại mỗi khi có thay đổi. Bằng cách truy vấn trực tiếp từ PostgreSQL tại thời điểm request, hệ thống luôn dùng dữ liệu mới nhất mà không cần lập chỉ mục lại. Ngoài ra, cách này cũng tuyệt đối ngăn rò rỉ dữ liệu giữa các khách hàng \- mỗi request chỉ truy vấn đúng user\_id của người hỏi.

### **5.2. Bước 1 \- Input Guardrail**

Input Guardrail là lớp bảo vệ đầu tiên, kiểm tra tin nhắn đầu vào trước khi xử lý bất kỳ logic nghiệp vụ nào. Thiết kế này tuân theo nguyên tắc lỗi nhanh \- chặn đầu vào không hợp lệ càng sớm càng tốt, tránh lãng phí tài nguyên cho các request không hợp lệ. Module thực hiện 3 loại kiểm tra tuần tự:

#### **5.2.1. Kiểm Tra Độ Dài**

Giới hạn tối đa 2000 ký tự/tin nhắn. Vượt ngưỡng sẽ bị từ chối ngay với thông báo rõ ràng. Ngưỡng 2000 ký tự được chọn vì đủ cho câu hỏi chi tiết nhất của khách hàng, đồng thời ngăn chặn payload injection cực dài có thể gây tràn cửa sổ ngữ cảnh của LLM.

#### **5.2.2. Phát Hiện Prompt Injection \- 20 Mẫu Regex**

Prompt injection là kỹ thuật tấn công trong đó kẻ xấu chèn chỉ thị giả vào tin nhắn để thao túng hành vi LLM. CreditIntel phòng chống bằng 20 mẫu regex song ngữ tiếng Anh và tiếng Việt:

| Nhóm | Số mẫu | Ví dụ | Mục đích tấn công |
| ----- | ----- | ----- | ----- |
| Vô hiệu hóa / ghi đè system prompt | 4 | "ignore all previous instructions" | Xóa quy tắc an toàn |
| Gán vai trò mới | 2 | "you are now a hacker" | Bypass giới hạn |
| Lộ system prompt | 6 | "reveal your system prompt" | Đánh cắp cấu hình |
| Xóa ngữ cảnh | 1 | "forget everything" | Reset trạng thái |
| Jailbreak | 2 | "jailbreak", "DAN mode" | Vượt rào bảo mật |
| Biến thể tiếng Việt | 5 | "bỏ qua các hướng dẫn ở trên" | Tấn công song ngữ |

Thiết kế phản hồi an toàn: khi phát hiện injection, phản hồi từ chối không tiết lộ lý do \- chỉ nói "Tôi chỉ hỗ trợ câu hỏi về khoản vay". Thiết kế này ngăn kẻ tấn công tinh chỉnh mẫu để né tránh.

Lý do dùng Regex thay vì LLM Classifier cho Guardrail: thứ nhất, tốc độ \- regex chạy trong microseconds, không cần gọi API. Thứ hai, xác định \- mẫu injection đã biết luôn bị bắt 100%, không phụ thuộc vào temperature của LLM. Hạn chế là không bắt được injection mới chưa có mẫu, nhưng với 20 mẫu bao phủ cả hai ngôn ngữ, đây là đánh đổi chấp nhận được cho ứng dụng tín dụng.

#### **5.2.3. Phát Hiện PII Probing \- 11 Mẫu Regex**

Bảo vệ chống truy vấn thông tin cá nhân của khách hàng khác \- bao gồm cả tiếng Việt và tiếng Anh. Khi phát hiện sẽ từ chối rõ ràng: "Vì lý do bảo mật, tôi chỉ hỗ trợ về hồ sơ vay của chính bạn."

#### **5.2.4. Cơ Chế Dừng Sớm**

Nếu bất kỳ kiểm tra nào trả về kết quả không hợp lệ, pipeline dừng ngay lập tức \- không gọi Intent Router, không gọi truy xuất, không gọi LLM. Câu trả lời an toàn được trả về trực tiếp, tiết kiệm toàn bộ chi phí API.

### **5.3. Bước 2 \- Phân Loại Ý Định (router.py)**

Intent Router phân loại câu hỏi thành 1 trong 6 loại ý định để quyết định chiến lược xử lý tiếp theo. Bước này đóng vai trò quan trọng vì nó quyết định có cần gọi truy xuất hay không \- tiết kiệm đáng kể chi phí cho các câu hỏi đơn giản.

#### **5.3.1. Sáu Loại Intent**

| Intent | Mô tả | Cần truy xuất? | Ví dụ |
| ----- | ----- | ----- | ----- |
| loan\_inquiry | Hỏi về khoản vay, trạng thái đơn | Có | "Trạng thái đơn vay của tôi?" |
| risk\_explanation | Hỏi về kết quả học máy, rủi ro | Có | "Tại sao tôi bị đánh giá HIGH?" |
| policy\_question | Hỏi về chính sách CreditIntel | Có | "DTI bao nhiêu là an toàn?" |
| personal\_advice | Xin tư vấn cải thiện tài chính | Có | "Làm sao giảm DTI?" |
| greeting | Chào hỏi, cảm ơn, small talk | Không | "Xin chào", "Cảm ơn" |
| off\_topic | Câu hỏi ngoài phạm vi | Không | "Thời tiết hôm nay?" |

#### **5.3.2. Kiến Trúc Hai Tầng: Regex Fast-path và LLM Fallback**

Module router sử dụng kiến trúc hai tầng có chủ đích:

Tầng 1 \- Regex Fast-path với 4 nhóm mẫu: Greeting gồm 9 mẫu như "xin chào", "hello", "cảm ơn", "bye"; Personal Risk gồm 5 mẫu như "xác suất vỡ nợ của tôi", "điểm mạnh và yếu trong hồ sơ"; Policy gồm 10 mẫu như "auto\_rejected", "bị từ chối", "DTI an toàn", "hạn mức tối đa"; Off-topic gồm 6 mẫu chỉ cho tin nhắn dưới 100 ký tự như "thời tiết", "bóng đá", "viết code".

Tầng 2 \- Phân loại LLM (Fallback): nếu không khớp mẫu nào, gọi Gemini 2.5 Flash với temperature=0 và max\_tokens=60, yêu cầu trả JSON có trường intent và confidence. Response được parse, validate intent thuộc danh sách hợp lệ, và fallback về "loan\_inquiry" nếu parse thất bại.

Hiệu quả của kiến trúc hai tầng: trong thực tế, ước tính khoảng 40% câu hỏi được xử lý bởi regex, tiết kiệm khoảng 40% chi phí router. Regex chạy trong microseconds, LLM mất 500ms đến 2 giây; LLM chỉ được gọi cho các câu hỏi mơ hồ mà regex không bao phủ được.

### **5.4. Bước 3 \- Retrieval Pipeline**

Bước truy xuất là cốt lõi kỹ thuật của hệ thống RAG, chịu trách nhiệm tìm các đoạn tài liệu liên quan nhất để cung cấp ngữ cảnh cho LLM. Pipeline truy xuất gồm 4 giai đoạn phễu, mỗi giai đoạn thu hẹp tập ứng viên theo thứ tự từ 20 xuống 12 xuống 4 parent sections.

#### **5.4.1. Giai Đoạn 3a \- Query Rewriting**

Trong hội thoại nhiều lượt, câu hỏi thường phụ thuộc ngữ cảnh \- chứa đại từ, thiếu chủ ngữ, hoặc ám chỉ thông tin từ lượt trước. Nếu dùng nguyên câu hỏi gốc để tìm kiếm, truy xuất sẽ cho kết quả kém vì vector embedding không hiểu ngữ cảnh hội thoại. Query Rewriter giải quyết bằng cách dùng LLM viết lại câu hỏi thành truy vấn độc lập:

| Lượt | Tin nhắn gốc | Sau khi viết lại |
| ----- | ----- | ----- |
| 1 (Người dùng) | "DTI của tôi bao nhiêu?" | Giữ nguyên (đã độc lập) |
| 2 (AI) | "DTI hiện tại là 45%..." | \- |
| 3 (Người dùng) | "Của tôi thì sao?" | "Xác suất vỡ nợ và mức rủi ro của đơn vay hiện tại" |

Query Rewriter chỉ kích hoạt khi có ngữ cảnh. Câu hỏi đầu tiên trong phiên giữ nguyên. Output được lọc để loại bỏ các trường hợp viết lại kém. Nếu viết lại thất bại, hệ thống dùng câu hỏi gốc làm phương án dự phòng.

#### **5.4.2. Giai Đoạn 3b \- Hybrid Search trên Qdrant**

Câu hỏi sau khi viết lại được mã hóa đồng thời bằng dense embedding qua API và sparse BM25 cục bộ, rồi gửi cho Qdrant tìm kiếm song song. Dense Search dùng cosine similarity trên vector 1536 chiều để hiểu paraphrase. Sparse BM25 khớp từ khóa chính xác để bắt được thuật ngữ viết tắt như DTI, CIC, FICO. Reciprocal Rank Fusion kết hợp xếp hạng từ cả hai, ưu tiên tài liệu xuất hiện ở đầu cả hai danh sách. Kết quả là top-20 child chunks \- lấy dư có chủ đích để đưa vào bước tái xếp hạng.

#### **5.4.3. Giai Đoạn 3c \- Cross-Encoder Reranking**

Hybrid Search dùng Bi-Encoder \- mã hóa câu hỏi và tài liệu riêng biệt rồi so sánh vector \- nhanh nhưng kém chính xác hơn Cross-Encoder vốn mã hóa cặp câu hỏi \- tài liệu cùng lúc với attention chéo giữa hai bên. CreditIntel áp dụng mô hình truy xuất trước \- tái xếp hạng sau:

| Tiêu chí | Bi-Encoder |  | Cross-Encoder |
| ----- | ----- | ----- | ----- |
| Tốc độ | Rất nhanh (1 lần mã hóa câu hỏi) |  | Chậm hơn (mã hóa N cặp) |
| Chính xác | Tốt nhưng không tối ưu |  | Rất chính xác (attention chéo) |
| Dùng khi | Lọc từ hàng nghìn tài liệu |  | Xếp hạng lại top-K nhỏ |
| **Thông số** | **Giá trị** | **Lý do** |  |
| Model | jina-reranker-v2-base-multilingual | Hỗ trợ tiếng Việt, chất lượng cao trên benchmark đa ngôn ngữ |  |
| Đầu vào | 20 child chunks | Từ Hybrid Search |  |
| Đầu ra | 12 child chunks | Đủ đa dạng cho mở rộng Parent, không quá nhiều |  |
| Vận hành | Inference cục bộ (\~1,1 GB RAM) | Không tốn API, bảo mật dữ liệu |  |

Lý do chạy Reranker cục bộ thay vì gọi API: thứ nhất, bảo mật \- nội dung tài liệu tín dụng nhạy cảm, không muốn gửi ra bên thứ ba. Thứ hai, chi phí \- không mất phí API mỗi request. Thứ ba, độ trễ ổn định \- không phụ thuộc mạng. Đổi lại, model chiếm khoảng 1,1 GB RAM và chạy trên CPU. Để giảm độ trễ request đầu tiên, model được khởi động trước khi server chạy thông qua mô hình Singleton.

#### **5.4.4. Giai Đoạn 3d \- Mở Rộng Tài Liệu Parent**

12 child chunks sau tái xếp hạng được ánh xạ ngược lên parent sections thông qua parent\_id trong siêu dữ liệu theo quy trình 5 bước: duyệt 12 child chunks theo thứ tự liên quan; với mỗi child, lấy parent\_id từ siêu dữ liệu; nếu parent\_id chưa xuất hiện thì thêm parent\_content vào danh sách kết quả; nếu parent\_id đã xuất hiện thì bỏ qua để tránh trùng lặp; dừng khi đạt 4 parent sections.

Nguyên tắc cốt lõi: nhiều child chunks có thể thuộc cùng 1 parent. Bước mở rộng gộp lại và trả về parent đầy đủ \- đảm bảo LLM nhận được ngữ cảnh rộng, không bị cắt ngang ý nghĩa. Đây là hiện thực hóa nguyên tắc của chiến lược Parent-Child: tìm ở mức chi tiết, trả về ở mức trọn vẹn.

#### **5.4.5. Tóm Tắt Retrieval Pipeline**

| Giai đoạn | Đầu vào \- Đầu ra | Thuật toán | Chi phí |
| ----- | ----- | ----- | ----- |
| Hybrid Search | 1 truy vấn \- 20 child chunks | Dense Cosine \+ BM25 \+ RRF | 1 lần gọi API embedding |
| Reranking | 20 \- 12 child chunks | Cross-Encoder scoring | Cục bộ (CPU, \~1,1 GB) |
| Mở rộng Parent | 12 child \- 4 parent sections | Ánh xạ siêu dữ liệu \+ loại trùng | Không tốn thêm |

### **5.5. Bước 4 \- Cá Nhân Hóa (personalizer.py)**

Trong các chatbot truyền thống, mọi khách hàng nhận được cùng giọng điệu phản hồi bất kể bối cảnh. CreditIntel cá nhân hóa sâu hơn: module Personalizer điều chỉnh giọng điệu và nội dung hướng dẫn dựa trên hai chiều là trạng thái đơn vay và ý định câu hỏi, tạo ra tổng cộng 7 nhân 6 bằng 42 tổ hợp cá nhân hóa.

#### **5.5.1. Ánh Xạ 7 Trạng Thái sang Tông Giọng**

| Trạng thái | Tông giọng | Ví dụ lời chào |
| ----- | ----- | ----- |
| auto\_rejected | Đồng cảm, khích lệ \- không trách móc | "Tôi hiểu đơn vay chưa đạt yêu cầu lần này..." |
| admin\_rejected | Đồng cảm, chuyên nghiệp | "Đơn vay gần nhất chưa được phê duyệt..." |
| pending\_review | Khích lệ, thông tin \- ước tính 1-3 ngày | "Đơn vay đang được xem xét..." |
| approved | Chúc mừng, hướng dẫn rõ ràng | "Chúc mừng bạn\!" |
| awaiting\_info | Hướng dẫn cụ thể từng bước | "Bước tiếp theo là nộp thông tin cá nhân..." |
| info\_submitted | Yên tâm, chuyên nghiệp | "Thông tin đã nộp thành công..." |
| None (chưa có đơn) | Thân thiện, chào đón | "Chào mừng đến với CreditIntel\!" |

#### **5.5.2. Hướng Dẫn Theo Intent**

Ngoài tông giọng theo trạng thái, Personalizer cung cấp hướng dẫn hành vi riêng cho mỗi intent: loan\_inquiry ưu tiên dữ liệu hồ sơ cá nhân, tài liệu chỉ bổ sung; risk\_explanation giải thích bằng ngôn ngữ dễ hiểu như nói "35%" thay vì ký hiệu kỹ thuật; policy\_question trả lời dựa trên tài liệu và trích dẫn nguồn; personal\_advice đưa ra khuyến nghị cụ thể và có thể hành động ví dụ như "DTI 45% \- trả bớt nợ X để giảm xuống dưới 35%"; greeting phản hồi ngắn gọn và giới thiệu là trợ lý tín dụng; off\_topic từ chối lịch sự và hướng dẫn quay lại chủ đề.

### **5.6. Bước 5 \- Sinh Văn Bản LLM (chain.py \+ prompts.py)**

Tất cả thông tin từ các bước trước được tổng hợp vào một prompt duy nhất gửi cho LLM. Bước này sử dụng LangChain LCEL với chuỗi ChatPromptTemplate, ChatOpenAI và StrOutputParser.

#### **5.6.1. Cấu Trúc Prompt 3 Phần**

Prompt được thiết kế theo cấu trúc 3 phần rõ ràng. Phần System Message gồm 9 quy tắc cốt lõi, thông tin cá nhân, giọng điệu từ Personalizer, hướng dẫn theo ý định, thông tin hồ sơ khách hàng 4 khối từ Context Builder, bản tóm tắt hội thoại trước từ Memory, và tài liệu liên quan là top-4 parent sections. Phần Chat History gồm các tin nhắn gần nhất trong ngân sách 2000 token. Phần Human Message là câu hỏi gốc \- không phải phiên bản viết lại, vì LLM cần hiểu đúng ý khách hàng thông qua ngữ cảnh hội thoại.

#### **5.6.2. 9 Quy Tắc Cốt Lõi trong System Prompt**

| \# | Quy tắc | Mục đích |
| ----- | ----- | ----- |
| 1 | Luôn trả lời tiếng Việt, thân thiện chuyên nghiệp | Nhất quán ngôn ngữ |
| 2 | Chỉ trả lời phạm vi tín dụng và tài chính | Ngăn off-topic |
| 3 | KHÔNG BAO GIỜ hứa phê duyệt đơn | Ngăn cam kết sai |
| 4 | KHÔNG tiết lộ thông tin khách khác, cấu trúc model | Bảo mật |
| 5 | Trích dẫn nguồn bằng tên file | Khả năng truy vết |
| 6 | Không chắc chắn \- nói rõ "không đủ thông tin" | Chống hallucination |
| 7 | Ưu tiên dữ liệu hồ sơ; tài liệu chỉ bổ trợ | Cá nhân hóa |
| 8 | Format Markdown: bullet riêng dòng, chữ đậm | Hiển thị đẹp trên giao diện |
| 9 | KHÔNG giả vờ đang chạy tính toán bất đồng bộ | Chống hallucination công cụ |

#### **5.6.3. Cấu Hình LLM**

| Thông số | Giá trị | Lý do lựa chọn |
| ----- | ----- | ----- |
| Model | google/gemini-2.5-flash | Nhanh, chi phí thấp, đủ chất lượng cho tư vấn |
| Temperature | 0,3 | Cân bằng: đủ chính xác không bịa, đủ tự nhiên không máy móc |
| Timeout | 30 giây | Đảm bảo trải nghiệm người dùng \- không để khách chờ quá lâu |
| Max retries | 2 | Thử lại tự động khi API lỗi tạm thời |
| API Gateway | OpenRouter | Truy cập nhiều model qua 1 API key thống nhất |

So sánh Temperature: 0,0 hoàn toàn xác định, dùng cho phân loại ý định; 0,3 nhất quán nhưng tự nhiên, dùng cho sinh văn bản; từ 0,7 trở lên sáng tạo, không phù hợp cho tư vấn tài chính vì có thể hallucinate thông tin.

### **5.7. Bước 6 \- Output Guardrail (guardrails.py)**

Output Guardrail là lớp bảo vệ cuối cùng, kiểm tra câu trả lời do LLM sinh ra trước khi trả về cho khách hàng. Dù system prompt đã yêu cầu LLM không tiết lộ thông tin nhạy cảm, LLM vẫn có thể sơ sót \- đặc biệt khi bị prompt injection phức tạp vượt qua Input Guardrail. Output Guardrail đóng vai trò lưới an toàn theo nguyên tắc phòng thủ theo chiều sâu.

#### **5.7.1 Phát Hiện Rò Rỉ Nội Bộ \- 14 Pattern** 

| Nhóm | Số pattern | Ví dụ phát hiện | Mục đích |
| ----- | ----- | ----- | ----- |
| Tên bảng DB | 4 | "Dữ liệu trong bảng loan\_applications..." | Ngăn lộ schema |
| SQL statements | 5 | "SELECT \* FROM users..." | Ngăn lộ query |
| API keys & secrets | 4 | "openrouter\_api\_key \= sk-..." | Ngăn lộ credentials |
| Model metadata | 1 | "model\_version: lgbm\_v4" | Ngăn lộ thông tin nội bộ |

#### **5.7.2 Phát Hiện Cam Kết Phê Duyệt \- 6 Pattern**

Nếu LLM vô tình cam kết phê duyệt ("Bạn chắc chắn sẽ được duyệt", "100% chance of approval"), câu trả lời không bị chặn nhưng được tự động đính kèm disclaimer:

Disclaimer tự động: "Lưu ý: Kết quả trên chỉ mang tính tư vấn. Quyết định phê duyệt cuối cùng luôn thuộc về bộ phận Admin của CreditIntel."

#### **5.7.3 Kiểm Tra Độ Dài**

Nếu câu trả lời vượt MAX\_OUTPUT\_LENGTH \= 3000 ký tự, thuật toán tìm dấu chấm/xuống dòng cuối cùng trước ngưỡng (phải nằm sau 60% nội dung) và cắt tại đó. Điều kiện 60% đảm bảo không cắt quá nhiều \- nếu câu hoàn chỉnh cuối cùng nằm ở đầu text (\< 60%), hệ thống cắt cứng tại 3000 ký tự.

#### **5.7.4 Bảng Tóm Tắt Output Guardrail**

| Loại kiểm tra | Số pattern | Mức độ | Hành vi |
| ----- | ----- | ----- | ----- |
| Rò rỉ nội bộ | 14 | Nghiêm trọng | Hard block \- thay toàn bộ câu trả lời |
| Cam kết phê duyệt | 6 | Trung bình | Soft fix \- đính kèm disclaimer |
| Quá dài | Ngưỡng 3000 chars | Nhẹ | Cắt thông minh tại câu hoàn chỉnh |

### **5.8. Ví Dụ End-to-End: "Tại sao đơn của tôi bị từ chối?"**

Để minh họa trọn vẹn 6 bước, xét câu hỏi tiêu biểu từ khách hàng có trạng thái auto\_rejected:

| Bước | Tên bước | Hành động & Kết quả |
| :---: | ----- | ----- |
| 1 | Input Guardrail | Kiểm tra: độ dài OK (35 ký tự \< 2000), không khớp 20 injection pattern, không khớp 11 PII pattern → PASS |
| 2 | Intent Router | Regex fast-path: khớp pattern "bị\\s+từ\\s+chối" → intent \= "policy\_question" (cần retrieval) |
| 3 | Retrieval | Query Rewrite → Hybrid Search (20 child chunks) → Cross-Encoder Rerank (12 chunks) → Parent Expansion: 4 parent sections từ policy.md và faq.md |
| 4 | Personalization | Trạng thái auto\_rejected → tông giọng "Đồng cảm và Khích lệ"; Intent policy\_question → "Trả lời dựa trên tài liệu, trích dẫn nguồn" |
| 5 | LLM Generation | Gemini 2.5 Flash (temperature=0.3): Prompt \= 9 rules \+ personalization \+ context \+ documents \+ history |
| 6 | Output Guardrail | Không rò rỉ nội bộ, không cam kết phê duyệt, độ dài \< 3000 ký tự → PASS → trả kết quả cho khách hàng |

## **6\. Nguồn tri thức: ba dòng ngữ cảnh**

Một đặc điểm kiến trúc quan trọng của CreditIntel là prompt cuối cùng được lắp ghép từ ba nguồn tri thức độc lập, mỗi nguồn trả lời một loại câu hỏi khác nhau. Việc tách bạch này được phản ánh trực tiếp trong template prompt (prompts.py) với các khối được phân cách rõ ràng.

### **6.1. Knowledge Base \- tri thức chính sách (tĩnh, dùng chung)**

Đây là kho tri thức được vector hóa trong Qdrant, nguồn cho khối TÀI LIỆU LIÊN QUAN. Kho bao gồm các tài liệu sau:

\- backend/rag/knowledge/policy.md \- Chính sách xét duyệt: phạm vi khoản vay ($500-$150,000; kỳ hạn 12/24/36/48/60 tháng), ba mức rủi ro, quy trình hai giai đoạn AI→Admin.

\- backend/rag/knowledge/faq.md \- Câu hỏi thường gặp, nhóm theo chủ đề (mô hình AI, AUTO\_REJECTED & CIC blacklist, DTI, quy trình…).

\- docs/data\_dictionary/\*.md \- Từ điển đặc trưng, giúp trợ lý giải thích các thuật ngữ dữ liệu.

Loader (ingest.load\_documents) quét đệ quy hai thư mục knowledge/ và docs/data\_dictionary/ theo glob \*\*/\*.md. Tri thức này dùng chung cho mọi khách hàng và chỉ thay đổi khi tài liệu nguồn được cập nhật và pipeline ingest được chạy lại.

## **6.2 User Context — Hồ sơ cá nhân động**

Trong kiến trúc hệ thống RAG được đề xuất, User Context đóng vai trò là nguồn tri thức quan trọng nhất tạo nên tính cá nhân hóa (personalization) của toàn bộ pipeline. Đây là nguồn dữ liệu được ưu tiên cao nhất trong quá trình sinh câu trả lời — theo quy tắc số 7 được quy định tường minh trong system prompt: "Với câu hỏi cá nhân, LUÔN ưu tiên THÔNG TIN HỒ SƠ KHÁCH HÀNG; TÀI LIỆU LIÊN QUAN chỉ là bổ trợ chính sách." Module context\_builder.py chịu trách nhiệm truy vấn đơn vay gần nhất của người dùng từ bảng loan\_applications trong hệ quản trị cơ sở dữ liệu quan hệ PostgreSQL, đồng thời tổng hợp và dựng bốn khối ngữ cảnh (4-block context matrix) theo đặc tả kỹ thuật được định nghĩa trong tài liệu docs/rag/rag\_ml\_context\_requirements.md.

Điểm khác biệt then chốt về mặt kiến trúc so với Knowledge Base tĩnh (đã trình bày tại mục 6.1) là: User Context không được nhúng (embed) vào cơ sở dữ liệu vector Qdrant, mà được truy vấn trực tiếp (live query) từ PostgreSQL tại thời điểm xử lý từng request, sau đó được bơm trực tiếp (inject) vào prompt của mô hình ngôn ngữ lớn (LLM). Quyết định thiết kế này xuất phát từ ba luận điểm kỹ thuật cốt lõi.

Luận điểm thứ nhất liên quan đến bản chất của dữ liệu: thông tin đơn vay mang tính trạng thái động (dynamic state), thay đổi liên tục theo vòng đời của đơn (tạo mới → chờ duyệt → phê duyệt/từ chối → cập nhật). Nếu nhúng dữ liệu này vào vector store, hệ thống sẽ vấp phải bài toán vector staleness — tức là vector đã được nhúng không còn phản ánh trạng thái mới nhất của đơn vay — từ đó đòi hỏi quá trình re-ingest liên tục, gây tốn chi phí embedding và gia tăng rủi ro bất đồng bộ dữ liệu giữa hai nguồn lưu trữ.

Luận điểm thứ hai liên quan đến mô hình truy vấn: kiến trúc Late Binding — tức là gắn kết dữ liệu tại thời điểm xử lý request thay vì tại thời điểm lập chỉ mục — đảm bảo tính nhất quán thời gian thực (real-time consistency) với độ trễ tối thiểu O(1) theo hằng số tra bảng cơ sở dữ liệu.

Luận điểm thứ ba liên quan đến bảo mật dữ liệu người dùng: phương pháp truy vấn trực tiếp theo user\_id thiết lập ranh giới cách ly thông tin chặt chẽ ở cấp độ ứng dụng, tuyệt đối ngăn chặn rò rỉ dữ liệu chéo giữa các khách hàng (cross-tenant data leakage). Bộ nhớ làm việc (working memory) của LLM chỉ được bơm các thông tin tương ứng với user\_id hiện hành — được xác thực qua JWT token — trong mỗi phiên xử lý độc lập.

Bốn khối ngữ cảnh cấu thành User Context được trình bày tổng quan trong Bảng 6.1 dưới đây và sẽ được phân tích chi tiết tại các mục 6.2.1 đến 6.2.4.

**Bảng 6.1. Bốn khối ngữ cảnh trong User Context**

| Khối | Nội dung | Nguồn |
| ----- | ----- | ----- |
| Form Context | Trạng thái đơn vay, số tiền yêu cầu, kỳ hạn, thu nhập hàng tháng, tỷ lệ nợ trên thu nhập (DTI), điểm tín dụng, tình trạng việc làm, tình trạng sở hữu nhà, dữ liệu lịch sử tín dụng từ CIC, các đặc trưng nhân khẩu học | Các trường dữ liệu của bản ghi LoanApplication trong PostgreSQL |
| ML Context | Xác suất vỡ nợ dự đoán (default\_probability), mức phân loại rủi ro (risk\_level), điểm an toàn (risk\_score \= (1 − p) × 100), hạn mức và kỳ hạn tối ưu do mô hình đề xuất, chuỗi định danh phiên bản mô hình (model\_version) | Kết quả suy luận từ pipeline Machine Learning được lưu trong PostgreSQL |
| Advisory Context | Các đặc trưng dẫn xuất được tính toán tại chỗ: so sánh số tiền/kỳ hạn với giá trị được đề xuất, phân dải DTI và điểm tín dụng, tối đa 4 yếu tố rủi ro chính, tối đa 4 điểm tích cực, danh sách khuyến nghị hành động ưu tiên | Tính toán xác định (deterministic) từ sự kết hợp của Form Context và ML Context |
| Data Quality Context | Số lượng trường bị hệ thống gán giá trị mặc định (imputed\_features), mức độ tin cậy tổng hợp (cao/trung bình/thấp), ghi chú điều chỉnh giọng điệu tư vấn tương ứng với từng mức tin cậy | Trường imputed\_features trong bản ghi LoanApplication |

### **6.2.1 Block 1 — Form Context (Ngữ cảnh biểu mẫu khách hàng)**

Form Context đóng vai trò thiết lập bức tranh tài chính cơ sở (financial baseline) của khách hàng, cung cấp cho LLM nền tảng dữ liệu nguyên thủy cần thiết để hiểu nhu cầu vay và đánh giá sơ bộ năng lực tài chính của người dùng trước khi tham chiếu tới bất kỳ đầu ra dự đoán nào từ mô hình học máy. Hàm \_build\_form\_context() trong module context\_builder.py thực hiện việc trích xuất trực tiếp các trường dữ liệu từ bản ghi LoanApplication, phân tổ chức thành năm nhóm thông tin có tính logic liên kết chặt chẽ, như trình bày trong Bảng 6.2.

**Bảng 6.2. Cấu trúc và vai trò của các nhóm trường dữ liệu trong Form Context**

| Nhóm thông tin | Các trường dữ liệu | Vai trò trong RAG |
| ----- | ----- | ----- |
| Khoản vay cốt lõi | loan\_amount, term, monthly\_income, dti, credit\_score | Cung cấp nền tảng định lượng để LLM đánh giá tính khả thi và mức độ rủi ro của khoản vay theo ngưỡng nghiệp vụ |
| Tình trạng việc làm | employment\_status, occupation\_type, years\_employed | Đánh giá độ ổn định và tính bền vững của nguồn thu nhập; các trạng thái trong tập \_STABLE\_EMPLOYMENT (Employed, Working, State servant, Commercial associate) được coi là chỉ số tín hiệu tích cực |
| Tài sản và mục đích vay | is\_homeowner, listing\_category | Cung cấp tín hiệu về mức độ ổn định tài chính thông qua tình trạng sở hữu nhà, và đánh giá tính phù hợp của mục đích vay theo chính sách sản phẩm |
| Lịch sử tín dụng (CIC) | num\_bureau\_records, num\_active\_credit, total\_overdue\_amount, max\_credit\_overdue\_days, has\_bad\_debt, income\_verifiable\_flag | Cung cấp bối cảnh lịch sử tín dụng ngoài hệ thống; nhận diện và cảnh báo các tình huống nợ quá hạn hoặc nợ xấu đang tồn tại |
| Đặc trưng nhân khẩu học | age\_years, gender, education\_ordinal, is\_married\_flag, cnt\_children, cnt\_fam\_members | Chỉ được LLM tham chiếu khi có chính sách nghiệp vụ rõ ràng liên quan; hệ thống hạn chế mô hình nhấn mạnh quá mức các yếu tố nhân khẩu học trong tư vấn |

Một đặc điểm thiết kế quan trọng cần nhấn mạnh là Form Context không chứa bất kỳ phép tính dẫn xuất hay suy luận nào — khối này chỉ phản ánh nguyên trạng dữ liệu đã được khách hàng khai báo hoặc hệ thống thu thập. Toàn bộ các suy luận nghiệp vụ liên quan — chẳng hạn như đánh giá mức DTI 45% là cao hay thấp so với ngưỡng chính sách — được ủy quyền hoàn toàn cho Block 3 (Advisory Context) theo nguyên tắc phân tách trách nhiệm (separation of concerns) trong kiến trúc hệ thống.

### **6.2.2 Block 2 — ML Context (Ngữ cảnh dự đoán từ mô hình học máy)**

ML Context là khối ngữ cảnh đóng vai trò cầu nối trực tiếp giữa kết quả suy luận của pipeline Machine Learning (được trình bày tại Chương IV) với lớp diễn giải ngôn ngữ tự nhiên trong kiến trúc RAG (Chương V). Hàm \_build\_ml\_context() trích xuất bảy trường dữ liệu đầu ra từ kết quả dự đoán đã được pipeline ML ghi nhận vào bản ghi LoanApplication trong PostgreSQL. Chi tiết của từng trường được trình bày trong Bảng 6.3.

**Bảng 6.3. Chi tiết các trường dữ liệu trong ML Context và cách thức sử dụng trong RAG**

| Trường dữ liệu | Kiểu dữ liệu | Ý nghĩa nghiệp vụ | Cách RAG sử dụng |
| ----- | ----- | ----- | ----- |
| default\_probability | float \[0, 1\] | Xác suất vỡ nợ dự đoán từ mô hình LightGBM; ngưỡng quyết định AUTO\_REVIEW\_THRESHOLD \= 0.4 — vượt ngưỡng này, đơn vay bị từ chối tự động | RAG diễn giải thành ngôn ngữ dễ hiểu: "Xác suất vỡ nợ ước tính khoảng 35%" thay vì phơi bày ký hiệu kỹ thuật P(default) \= 0.35; được dùng để giải thích lý do chấp nhận hoặc từ chối đơn vay |
| risk\_level | str ∈ {Low, Medium, High} | Phân khúc rủi ro rời rạc (categorical) suy ra từ default\_probability theo ngưỡng nghiệp vụ đã được định nghĩa | RAG sử dụng để điều chỉnh giọng điệu phản hồi tương ứng (đồng cảm với High, khích lệ cải thiện với Medium, chúc mừng với Low) thông qua module personalizer.py |
| risk\_score | int \[0, 100\] | Điểm an toàn (safety score) được tính theo công thức (1 − default\_probability) × 100; điểm càng cao phản ánh mức độ an toàn càng lớn — ngược chiều với trực giác thông thường | RAG trình bày kèm chú thích giải thích chiều đọc: "Risk score: 57/100 (càng cao càng an toàn)"; template \_json\_to\_text() luôn đính kèm dòng chú thích này để phòng ngừa hiểu nhầm |
| recommended\_amount | float | Hạn mức vay tối ưu do mô hình ML đề xuất, được suy ra từ phân tích đa biến trên DTI, điểm tín dụng, thu nhập và lịch sử tín dụng | RAG so sánh trực tiếp với loan\_amount trong Advisory Context (Block 3\) để tư vấn khách hàng về việc điều chỉnh số tiền vay |
| recommended\_term | int | Kỳ hạn vay tối ưu tính bằng tháng, thuộc tập giá trị hợp lệ {12, 24, 36, 48, 60} | Tương tự recommended\_amount; được sử dụng trong Advisory Context để đề xuất điều chỉnh kỳ hạn phù hợp với năng lực tài chính |
| model\_version | str | Chuỗi định danh phiên bản mô hình, ví dụ "customer\_lgbm\_v4\_stability" | Phục vụ mục đích truy vết (traceability) và kiểm toán hệ thống: khi cần xác minh tính chính xác của câu trả lời RAG, có thể truy ngược phiên bản mô hình đã sinh ra dự đoán tương ứng |
| has\_prediction | bool | Cờ nhị phân cho biết đơn vay đã có kết quả ML hay chưa (True khi default\_probability is not None) | RAG kiểm tra cờ này trước khi render Block 2; nếu False, hệ thống chỉ hiển thị thông báo "Chưa có kết quả ML cho đơn này" thay vì render các trường rỗng gây nhầm lẫn |

#### **6.2.2.1 Luồng dữ liệu từ ML Pipeline đến RAG**

Kết quả dự đoán của mô hình không được chuyển tiếp trực tiếp từ quá trình suy luận vào prompt của RAG, mà đi qua chuỗi xử lý có kiểm soát gồm năm bước: (1) mô hình LightGBM hoàn thành suy luận qua ml\_service.predict(); (2) kết quả được ghi nhận vào bảng loan\_applications trong PostgreSQL; (3) hàm context\_builder.\_build\_ml\_context() đọc dữ liệu từ PostgreSQL; (4) hàm \_json\_to\_text() định dạng cấu trúc dữ liệu thành văn bản có cấu trúc rõ ràng; và (5) văn bản kết quả được inject vào biến {user\_context} trong system prompt trước khi gửi đến LLM.

Thiết kế theo chuỗi xử lý trung gian này hiện thực hóa nguyên tắc tách biệt mối quan tâm (separation of concerns) ở mức độ cao: mô hình ML không cần biết sự tồn tại của lớp RAG, và RAG không cần biết quy trình huấn luyện hay kiến trúc nội tại của mô hình. Điểm giao tiếp duy nhất giữa hai pipeline là tập hợp các trường dữ liệu đã được chuẩn hóa trong bảng loan\_applications, hoạt động như một hợp đồng dữ liệu (data contract) tường minh, bảo đảm tính độc lập, khả năng bảo trì và khả năng thay thế của từng thành phần mà không gây ảnh hưởng đến toàn hệ thống.

#### **6.2.2.2 Nguyên tắc diễn giải kết quả ML theo mức rủi ro**

Theo đặc tả kỹ thuật trong docs/rag/rag\_ml\_context\_requirements.md, RAG phải tuân thủ các ranh giới diễn giải nghiêm ngặt tương ứng với từng mức risk\_level. Bảng 6.4 trình bày chi tiết các phát ngôn được phép và bị cấm đối với mỗi mức rủi ro, nhằm đảm bảo tính nhất quán, trách nhiệm giải trình và tránh gây hiểu nhầm cho người dùng cuối.

**Bảng 6.4. Ranh giới diễn giải kết quả ML theo mức phân loại rủi ro**

| Mức rủi ro | RAG có thể diễn đạt | RAG không được diễn đạt |
| ----- | ----- | ----- |
| Low | Hồ sơ có rủi ro thấp theo đánh giá ML; khoản vay có khả năng phù hợp với năng lực tài chính; có thể cân nhắc hạn mức và kỳ hạn theo đề xuất; phán quyết cuối cùng vẫn thuộc thẩm quyền của chuyên viên xét duyệt (Admin) | "Bạn chắc chắn được phê duyệt"; "Ngân hàng sẽ giải ngân cho bạn" — bởi RAG không có thẩm quyền thay thế quyết định tín dụng của con người |
| Medium | Hồ sơ ở mức cần xem xét bổ sung; nên đối chiếu số tiền yêu cầu với recommended\_amount; chuyên viên xét duyệt có thể yêu cầu cung cấp thêm tài liệu hoặc thông tin xác minh | — |
| High | Mô hình ML đánh giá mức rủi ro cao, khoản vay hiện tại thường không phù hợp với năng lực tài chính; nêu cụ thể các yếu tố cần cải thiện; khuyến nghị giảm số tiền vay hoặc tăng cường hồ sơ trước khi nộp lại | Đề xuất tăng gói vay; khuyến khích vay thêm trong khi mức rủi ro đang ở ngưỡng cao |

Ngoài ra, RAG phải diễn giải kết quả ML theo hướng tương quan nhân tố (correlational framing) thay vì khẳng định quan hệ nhân quả tuyệt đối. Cụ thể, hệ thống nên sử dụng cách diễn đạt như "Các yếu tố có thể làm tăng rủi ro trong hồ sơ của bạn là..." thay vì "Bạn bị từ chối vì đúng một lý do duy nhất là..."; đồng thời nên thêm điều kiện bất định như "Nếu thông tin khai báo chưa đầy đủ, kết quả có thể chưa phản ánh toàn bộ tình hình tài chính" thay vì khẳng định tuyệt đối tính đúng đắn của mô hình. Nguyên tắc này phản ánh giới hạn nhận thức luận của bất kỳ mô hình học máy nào và đảm bảo tính minh bạch trong truyền thông rủi ro.

### **6.2.3 Block 3 — Advisory Context (Ngữ cảnh tư vấn suy diễn)**

Advisory Context là khối ngữ cảnh đặc biệt nhất trong kiến trúc User Context. Không giống như các khối còn lại, khối này không trích xuất từ bất kỳ nguồn dữ liệu lưu trữ nào, mà được sinh tại chỗ (computed on-the-fly) bằng một cơ chế suy luận xác định (deterministic rule engine) được triển khai trong hàm \_build\_advisory\_context() của module context\_builder.py. Cơ chế này kết hợp thông tin từ Form Context (Block 1\) và ML Context (Block 2\) để suy ra các đặc trưng dẫn xuất (derived features) phục vụ trực tiếp cho chức năng tư vấn tài chính.

Bảng 6.5 trình bày đầy đủ các thành phần cấu thành Advisory Context cùng với công thức tính toán hoặc logic suy luận tương ứng và mục đích tư vấn của từng thành phần.

**Bảng 6.5. Cấu trúc, công thức và mục đích tư vấn của các thành phần trong Advisory Context**

| Thành phần | Công thức / Logic suy luận | Mục đích tư vấn |
| ----- | ----- | ----- |
| loan\_vs\_recommended | (loan\_amount − recommended\_amount) / recommended\_amount × 100; phân ba vùng: Cao hơn đề xuất (\> 10%), Phù hợp (±10%), Thấp hơn (\< −10%) | Cung cấp cho LLM đánh giá định lượng về mức độ tương thích giữa số tiền yêu cầu và năng lực tài chính thực tế của khách hàng |
| term\_vs\_recommended | So sánh trực tiếp giá trị term với recommended\_term | Cung cấp căn cứ để đề xuất điều chỉnh kỳ hạn nếu kỳ hạn đang chọn không tương thích với rủi ro đánh giá |
| loan\_to\_monthly\_income | loan\_amount / monthly\_income | Đánh giá quy mô khoản vay tương đối so với năng lực tạo thu nhập hàng tháng |
| loan\_to\_annual\_income | loan\_amount / (monthly\_income × 12\) | Đánh giá khả năng vay và hoàn trả theo góc nhìn thu nhập năm |
| dti\_band | Tra bảng \_DTI\_BANDS: Tốt (\< 30%), Cần chú ý (30%–43%), Rủi ro cao (\> 43%) | Diễn giải chỉ số DTI bằng ngôn ngữ định tính có ngữ nghĩa rõ ràng thay vì số thập phân thuần túy |
| credit\_score\_band | Tra bảng \_CREDIT\_BANDS: Kém (\< 580), Trung bình (580–669), Tốt (670–739), Rất tốt (740–799), Xuất sắc (≥ 800\) | Phân loại điểm tín dụng theo thang chuẩn phổ biến, giúp LLM tham chiếu chính xác trong tư vấn cải thiện hồ sơ |
| primary\_risk\_factors | Tối đa 4 yếu tố rủi ro chính, suy ra từ các điều kiện tường minh: if dti \> 0.43, if cs \< 580, if loan \> rec × 1.1, if has\_bad\_debt, if max\_overdue\_days \> 60, if total\_overdue \> 0 | Cung cấp 2–4 nguyên nhân chủ yếu làm tăng rủi ro khoản vay, giúp LLM giải thích cụ thể và có căn cứ thay vì nhận định chung chung |
| positive\_factors | Tối đa 4 điểm tích cực: if is\_homeowner, if dti \< 0.30, if cs \>= 740, if income\_verifiable, if stable\_employment, if years\_employed \>= 3, if has\_bad\_debt is False | Cân bằng nội dung phản hồi — ghi nhận điểm mạnh của hồ sơ song song với việc nêu rủi ro, đảm bảo tính công bằng và khách quan trong tư vấn |
| suggested\_actions | Danh sách khuyến nghị hành động ưu tiên, được sinh từ tập luật xác định: giảm số tiền vay, giảm DTI, cải thiện điểm tín dụng, xử lý nợ xấu, tăng cường hồ sơ tổng thể | Hướng dẫn khách hàng thực hiện các bước cụ thể, có thể hành động (actionable) để cải thiện khả năng được phê duyệt trong lần nộp tiếp theo |

Đặc điểm thiết kế cốt lõi của Advisory Context là toàn bộ logic suy luận được triển khai bằng luật xác định (deterministic rule) ở tầng Python, không phải bằng LLM. Cụ thể, các chỉ số DTI được phân dải thông qua bảng tra \_DTI\_BANDS với ngưỡng cứng (Tốt \< 30%, Cần chú ý 30–43%, Rủi ro cao \> 43%); các yếu tố rủi ro và điểm tích cực được suy ra bằng các biểu thức điều kiện tường minh như if dti \> 0.43 hay if cs \>= 740\. Nhờ cách thiết kế này, LLM nhận được một bản phân tích đã được chuẩn hóa và định lượng đầy đủ, thay vì phải tự suy luận từ số liệu thô — từ đó giảm mạnh nguy cơ tính toán sai lệch hoặc bịa đặt các con số tài chính không có trong dữ liệu gốc.

Lý do học thuật đằng sau quyết định này là: nếu để LLM tự đánh giá liệu một giá trị DTI cụ thể là cao hay thấp, kết quả sẽ thiếu nhất quán giữa các lượt do tham số temperature \> 0 trong quá trình sinh văn bản. Bằng cách tính toán sẵn các dải phân loại và yếu tố rủi ro ở tầng ứng dụng, hệ thống đảm bảo rằng mọi câu trả lời đều dựa trên cùng một bộ ngưỡng nghiệp vụ thống nhất, đồng thời cho phép kiểm thử đơn vị (unit test) khối Advisory Context độc lập với LLM. Về bản chất, Advisory Context hoạt động như một lớp chuyển ngữ (translation layer) biến đổi các tham số kỹ thuật thô thành logic tư vấn tài chính có cấu trúc, từ đó triệt tiêu hiện tượng ảo giác (hallucination) của LLM trong các phép tính toán học và suy luận luật kinh doanh phức tạp.

### **6.2.4 Block 4 — Data Quality Context (Ngữ cảnh chất lượng dữ liệu)**

Khối thứ tư và cuối cùng trong cấu trúc User Context đóng vai trò là hệ số bất định (uncertainty factor) định lượng độ tin cậy cho toàn bộ phân tích được sinh ra bởi ba khối trước. Hàm \_build\_quality\_context() kiểm tra trường imputed\_features — danh sách các đặc trưng mà pipeline ML đã phải gán giá trị mặc định (impute) do khách hàng không cung cấp đầy đủ hoặc dữ liệu đầu vào bị thiếu trong quá trình thu thập. Dựa trên số lượng trường bị impute, hệ thống phân loại mức độ tin cậy thành ba bậc như trình bày trong Bảng 6.6.

**Bảng 6.6. Phân loại mức độ tin cậy dữ liệu và nội dung chú thích inject vào prompt**

| Số trường bị impute | Mức độ tin cậy | Nội dung chú thích inject vào prompt |
| ----- | ----- | ----- |
| 0 | Cao | "Tất cả thông tin do khách hàng cung cấp trực tiếp." — LLM có thể đưa ra nhận định với mức độ tự tin cao hơn |
| 1 – 2 | Trung bình | "Một số dữ liệu được hệ thống gán mặc định (ví dụ: age\_years, ext\_source\_1). Kết quả tư vấn có thể chưa phản ánh toàn bộ tình hình tài chính của khách hàng." |
| ≥ 3 | Thấp | "Nhiều trường dữ liệu được hệ thống gán mặc định (...). Nên sử dụng ngôn ngữ thận trọng trong tư vấn và khuyến khích khách hàng cung cấp thêm thông tin." |

Cơ chế chú thích mức tin cậy này cung cấp tín hiệu kiểm soát (guardrail signal) cho LLM: khi mức tin cậy ở mức thấp hoặc trung bình, mô hình ngôn ngữ sẽ chủ động điều chỉnh sang giọng điệu thận trọng hơn — ví dụ sử dụng các cụm từ như "Dựa trên thông tin hiện có..." hoặc "Nếu thông tin khai báo chưa đầy đủ..." — thay vì khẳng định tuyệt đối. Đây là biện pháp phòng ngừa ảo giác (anti-hallucination guardrail) hoạt động ở cấp độ ngữ cảnh đầu vào, bổ trợ trực tiếp cho cơ chế kiểm soát đầu ra (Output Guardrail) ở cấp độ văn bản kết quả.

### **6.2.5 Định dạng cuối cùng khi inject vào prompt**

Hàm \_json\_to\_text() chịu trách nhiệm chuyển đổi cấu trúc dữ liệu JSON của 4-block context thành văn bản có cấu trúc rõ ràng, sẵn sàng để inject vào biến {user\_context} trong system prompt. Định dạng tuân theo mẫu đặc tả trong Section 4 của tài liệu rag\_ml\_context\_requirements.md. Cấu trúc văn bản phẳng (plain structured text) với dấu gạch đầu dòng được chọn thay vì JSON hay XML, xuất phát từ lý do thực nghiệm: mô hình Gemini 2.5 Flash xử lý và hiểu ngữ nghĩa tốt hơn với định dạng văn bản có danh sách rõ ràng, đồng thời giúp người vận hành dễ dàng quan sát và gỡ lỗi khi kiểm tra log prompt trong quá trình vận hành.

Ví dụ minh họa đầu ra thực tế của \_json\_to\_text() khi được inject vào prompt cho một trường hợp khách hàng có đơn vay thuộc mức rủi ro cao được trình bày trong Bảng 6.7 dưới đây.

**Bảng 6.7. Ví dụ đầu ra thực tế của User Context khi render vào prompt LLM**

| Khối | Nội dung văn bản inject |
| ----- | ----- |
| THÔNG TIN ĐƠN VAY GẦN NHẤT (Form Context) | Trạng thái đơn: PENDING\_REVIEW Số tiền xin vay: $20,000 | Kỳ hạn: 36 tháng Thu nhập hàng tháng: $12,000 DTI: 46.0% — Rủi ro cao (\> 43%) Điểm tín dụng: 610 — Trung bình (580–669) Tình trạng việc làm: Employed Sở hữu nhà: Không | Mục đích vay: debt consolidation Lịch sử tín dụng: 5 hồ sơ | 2 đang hoạt động | Nợ xấu: Không |
| KẾT QUẢ ML (ML Context) | Xác suất vỡ nợ dự đoán: 43.2% Mức rủi ro: High Risk score: 57/100 (càng cao càng an toàn) Hạn mức đề xuất: $3,000 / 12 tháng So sánh số tiền: Cao hơn đề xuất 567% ($20,000 so với $3,000) So sánh kỳ hạn: Kỳ hạn chọn (36 tháng) dài hơn đề xuất (12 tháng) |
| PHÂN TÍCH TƯ VẤN (Advisory Context) | Yếu tố rủi ro chính: • DTI quá cao (\> 43%) — tỷ lệ nợ/thu nhập nặng • Điểm tín dụng trung bình (580–669), chưa đủ mạnh • Số tiền vay cao hơn hạn mức đề xuất ($20,000 \> $3,000) Điểm tích cực: • Có việc làm ổn định • Không có lịch sử nợ xấu Khuyến nghị: • Cân nhắc giảm số tiền vay về mức đề xuất ($3,000) • Giảm DTI bằng cách trả bớt nợ hiện tại trước khi vay thêm • Cải thiện điểm tín dụng thông qua thanh toán đúng hạn |
| ĐỘ TIN CẬY DỮ LIỆU (Data Quality Context) | Mức độ tin cậy: Trung bình Một số dữ liệu được hệ thống gán mặc định (age\_years, ext\_source\_1, ext\_source\_3). Kết quả tư vấn có thể chưa phản ánh toàn bộ tình hình tài chính của khách hàng. |

### **6.2.6 Tổng kết vai trò của User Context trong kiến trúc RAG**

Xét về mặt kiến trúc tổng thể, User Context tạo ra một cơ chế định vị kép (dual-grounding mechanism) cho hệ thống RAG, trong đó hai nguồn định vị hoạt động song song và bổ trợ lẫn nhau để đảm bảo chất lượng câu trả lời trong mọi tình huống truy vấn.

Định vị thứ nhất đến từ Knowledge Base tĩnh (Static Grounding): LLM trả lời các câu hỏi liên quan đến chính sách, quy trình và thông tin sản phẩm dựa trên nội dung được truy xuất từ các tài liệu policy.md và faq.md thông qua cơ sở dữ liệu vector Qdrant. Nguồn định vị này đảm bảo tính nhất quán và độ chính xác thực tế (factual accuracy) của các phát ngôn liên quan đến chính sách tín dụng và điều khoản sản phẩm.

Định vị thứ hai đến từ User Context động (Dynamic Grounding): LLM trả lời các câu hỏi về hồ sơ cá nhân, kết quả đánh giá ML và đề xuất cải thiện dựa trên 4-block context được inject trực tiếp vào prompt. Nguồn định vị này đảm bảo tính cá nhân hóa và phù hợp ngữ cảnh của câu trả lời với từng khách hàng cụ thể.

Sự phân tách rõ ràng giữa hai cơ chế định vị này giải thích một hiện tượng đáng chú ý trong kết quả đánh giá hệ thống tại mục 5.8: nhóm câu hỏi cá nhân hóa (personalized queries) có chỉ số Context Precision bằng 0 — tức là không có tài liệu nào được truy xuất từ Qdrant đóng góp vào câu trả lời — nhưng hệ thống vẫn trả lời đúng và có độ chính xác cao. Hiện tượng này không phải là lỗi của pipeline truy xuất, mà là hệ quả trực tiếp và tất yếu của kiến trúc dual-grounding: các câu hỏi cá nhân hóa được định vị từ User Context chứ không phải từ tài liệu KB, và do đó không cần đến cơ chế truy xuất vector.

### **6.3. Chat Memory \- bộ nhớ hội thoại (động, theo phiên)**

Nguồn thứ ba là lịch sử hội thoại, phục vụ khối TÓM TẮT HỘI THOẠI TRƯỚC ĐÓ và placeholder chat\_history. Module memory.py triển khai chiến lược cửa sổ trượt kết hợp đệm tóm tắt lười (sliding window \+ lazy summary buffer), được trình bày chi tiết tại Mục 7.1.

### **6.4. Lắp ghép prompt cuối cùng**

Sáu biến được bơm vào SYSTEM\_TEMPLATE (prompts.py): tên khách hàng, hướng dẫn giọng điệu, hướng dẫn theo ý định, hồ sơ khách hàng (User Context), tóm tắt hội thoại, và tài liệu liên quan (Knowledge Base); cùng với lịch sử hội thoại (chat\_history) và câu hỏi hiện tại, toàn bộ ChatPromptTemplate có tám biến. Quy tắc số 7 trong system prompt nêu rõ thứ tự ưu tiên: với câu hỏi cá nhân, hệ thống luôn ưu tiên thông tin hồ sơ khách hàng, trong khi tài liệu liên quan chỉ đóng vai trò bổ trợ chính sách. Đây là cơ chế hòa giải khi hai nguồn tri thức có thể mâu thuẫn nhau.

## **7\. Kỹ thuật nâng cao**

Ba kỹ thuật trình bày trong mục này là những gì nâng trợ lý CreditIntel vượt lên trên một chatbot hỏi-đáp thông thường: bộ nhớ hội thoại cho phép hệ thống nhớ và nối mạch câu chuyện qua nhiều lượt, công cụ điều chỉnh khoản vay cho phép hệ thống hành động thay vì chỉ cung cấp thông tin, và mẫu khởi tạo an toàn đa luồng cho phép phục vụ nhiều người dùng đồng thời một cách hiệu quả.

### **7.1. Chat Memory: cửa sổ trượt kết hợp đệm tóm tắt lười**

Một hội thoại càng kéo dài thì prompt càng phình to và càng tốn token, nhưng cắt cụt lịch sử lại khiến trợ lý quên mất ngữ cảnh của người dùng. Hàm load\_memory trong memory.py hóa giải mâu thuẫn này bằng cách kết hợp hai cơ chế bổ sung cho nhau.

Cơ chế thứ nhất là cửa sổ trượt theo ngân sách token. Hệ thống lấy toàn bộ tin nhắn của phiên (bỏ qua các tin bị đánh dấu lỗi), rồi để hàm \_split\_window duyệt từ tin mới nhất ngược về quá khứ, cộng dồn chi phí token ước lượng thô theo công thức len(text) // 4, cho tới khi chạm trần ngân sách rag\_memory\_window\_token\_budget là 2.000 token. Phần "gần đây" nằm trong cửa sổ đó được đưa nguyên văn vào biến chat\_history của prompt. Một chi tiết bảo vệ tinh tế là lượt mới nhất không bao giờ bị loại bỏ, kể cả khi tự thân nó đã vượt ngân sách, nhằm đảm bảo câu hỏi vừa được đặt ra luôn hiện diện trong ngữ cảnh.

Cơ chế thứ hai là đệm tóm tắt lười (lazy summary buffer), xử lý phần hội thoại cũ hơn cửa sổ. Thay vì bỏ đi phần đó, hệ thống nén nó thành một bản tóm tắt tiếng Việt lưu trong cột session.summary của cơ sở dữ liệu. Cơ chế được gọi là "lười" vì nó chỉ thực sự gọi LLM tóm tắt khi hai điều kiện cùng thỏa: số tin cũ chưa được tóm tắt phải đạt ngưỡng rag\_memory\_min\_messages\_to\_summarize là sáu tin, và bản tóm tắt hiện có phải chưa bao phủ tới tin cũ nhất (kiểm tra qua con trỏ summary\_covers\_until\_id). Khi cả hai điều kiện thỏa, một LLM riêng (temperature=0.2, max\_tokens=500) được gọi để hợp nhất bản tóm tắt cũ với các lượt mới thành một bản tóm tắt bao trùm. Việc ghi bản tóm tắt mới được thực hiện có giao dịch: nếu lệnh commit thất bại, toàn bộ trạng thái-nội dung, con trỏ bao phủ và mốc thời gian-được khôi phục về giá trị cũ.

Quyết định thiết kế: Nếu tóm tắt sau mỗi tin nhắn, hệ thống sẽ phải trả thêm một lời gọi LLM cho từng lượt chat, vừa chậm vừa tốn kém. Bằng cách chờ tích lũy đủ sáu tin cũ và chỉ tóm tắt khi bản tóm tắt hiện tại đã "lỗi thời", hệ thống cắt giảm phần lớn chi phí mà vẫn giữ được ngữ cảnh dài hạn. Tuân theo triết lý suy giảm duyên dáng, khi việc tóm tắt thất bại thì lượt chat không bị gián đoạn: hệ thống chỉ giữ lại bản tóm tắt cũ và ghi một dòng cảnh báo vào log.

### **7.2. Loan Adjustment Tool: RAG mang khả năng hành động**

Tính năng điều chỉnh khoản vay là bước nhảy biến trợ lý từ một cỗ máy trả lời thành một tác nhân có khả năng hành động thực sự. Khi một đơn vay rơi vào trạng thái AUTO\_REJECTED, thay vì chỉ giải thích nguyên nhân từ chối, trợ lý có thể tự mô phỏng các phương án khả thi và nộp lại đơn thay cho khách hàng. Phần logic cốt lõi nằm trong services/loan\_adjustment\_tool.py và được điều phối bởi chat\_service.py.

Quá trình bắt đầu từ việc phát hiện ý định. Hàm \_is\_loan\_adjustment\_request sử dụng một bộ quy tắc từ khóa tiếng Việt, bao gồm cả các biến thể không dấu, để nhận ra những yêu cầu như "đề xuất gói vay phù hợp", "nộp lại đơn" hay "đổi kỳ hạn nào để được duyệt". Đáng chú ý là tập từ khóa này còn bao gồm chính những cụm mà trợ lý tự gợi ý làm nút trả lời nhanh-ví dụ "gói vay phù hợp" hay "đề xuất phương án"-nhằm khép kín vòng lặp tương tác người-máy: khách hàng chỉ cần bấm vào gợi ý của AI là kích hoạt được công cụ.

Khi ý định đã được xác nhận, hàm find\_best\_reapplication\_option dựng tập ứng viên từ hai nguồn rồi hợp nhất, thay vì thử tuần tự từng chiến lược rồi dừng sớm. Nguồn thứ nhất là một bộ đề xuất mềm bằng LLM (loan\_adjustment\_reasoner, bật/tắt qua cờ rag\_loan\_reasoner\_enabled): từ một bản tóm tắt rủi ro tất định của đơn bị từ chối (DTI, nợ hàng tháng, thu nhập, nợ xấu…), nó gọi gemini-2.5-flash ở temperature=0 để đề xuất tối đa sáu phương án (số tiền, kỳ hạn, chiến lược, lý do) dưới dạng JSON, với ràng buộc chỉ được giảm số tiền và chỉ giữ nguyên hoặc kéo dài kỳ hạn; mọi lỗi gọi hàm hay JSON hỏng đều khiến nó trả về danh sách rỗng để lui an toàn về lưới cứng. Nguồn thứ hai là lưới cứng tất định (\_grid\_candidates): nhánh kéo dài kỳ hạn thử các mốc dài hơn trong tập {12, 24, 36, 48, 60} tháng, còn nhánh giảm số tiền cố định ở kỳ hạn 60 tháng rồi thử hạn mức đề xuất cùng các mốc 75%, 50%, 25% của số tiền ban đầu và mức sàn 500 đô-la. Hàm merge\_candidates gộp hai nguồn (ưu tiên ứng viên LLM), làm sạch và khử trùng. Điểm mấu chốt về độ tin cậy là mọi ứng viên-bất kể từ LLM hay lưới cứng-đều được đưa trở lại đúng mô hình ML production qua ml\_service.predict trong một lượt quét duy nhất (không còn dừng sớm theo stage) để lấy xác suất vỡ nợ thực, không phải con số phỏng đoán. Một ứng viên chỉ được coi là đạt khi xác suất vỡ nợ nằm dưới ngưỡng AUTO\_REVIEW\_THRESHOLD (0.4) và đồng thời vượt qua bộ kiểm tra validate\_confirmed\_values. Các phương án đạt được xếp hạng bằng một khoá thống nhất ưu tiên thay đổi ít nhất so với đơn gốc (\_unified\_rank), trả về tối đa ba phương án; mỗi phương án mang nhãn chiến lược extend\_term, reduce\_amount hoặc both cùng một câu lý do (rationale) được đưa vào ngữ cảnh RAG. Khi không có ứng viên nào lọt ngưỡng, hệ thống chuyển sang fallback\_proposal, trình bày ba biểu mẫu tốt nhất kèm cảnh báo minh bạch rằng chúng vẫn cần admin duyệt thủ công.

Các phương án tìm được được tiêm vào ngữ cảnh LLM thông qua \_format\_loan\_adjustment\_context, kèm một chỉ dẫn yêu cầu LLM trình bày các phương án như sự thật đã được tính sẵn, đồng thời hướng dẫn khách hàng nhắn "Đồng ý" hoặc "Xác nhận" để nộp, hay "Hủy" để bỏ. Quy tắc số 9 trong system prompt cấm tuyệt đối LLM giả vờ "đang chạy tính toán nền", bởi mọi phương án phải có sẵn ngay trong lượt hiện tại. Toàn bộ thao tác nộp lại được bảo vệ bằng vòng xác nhận có trạng thái: phương án được lưu vào session.pending\_action với thời gian sống 30 phút. Ở lượt kế tiếp, hàm \_handle\_pending\_loan\_adjustment\_response đọc câu trả lời của khách; nếu phủ định thì hủy bỏ, nếu khẳng định thì \_confirm\_pending\_loan\_adjustment gọi application\_service.confirm để tạo đơn vay mới-chỉ thay đổi số tiền và kỳ hạn, giữ nguyên mọi số liệu còn lại-rồi báo lại mã đơn mới cùng xác suất vỡ nợ tương ứng. Hồ sơ bị từ chối cũ tuyệt đối không bao giờ bị sửa đổi, đảm bảo tính toàn vẹn của lịch sử.

Quyết định thiết kế: Nếu để LLM tự đoán kỳ hạn nào sẽ được duyệt rồi hứa luôn với khách, đó chính là mảnh đất màu mỡ cho ảo giác và những lời hứa sai. Kiến trúc hiện tại cho LLM một vai trò có ích nhưng bị kiểm soát chặt: nó được phép đề xuất ứng viên (gợi ý giảm tiền hay kéo dài kỳ hạn theo yếu tố rủi ro chính), song mỗi đề xuất ấy-cùng toàn bộ lưới cứng-đều phải chạy qua chính mô hình đang vận hành trong production, và công cụ chỉ trình bày những phương án đã được kiểm chứng nằm dưới ngưỡng 0.4. Nói cách khác, LLM đề xuất nhưng mô hình ML mới là bên quyết định phương án nào đủ an toàn để hiện ra; quyền ra quyết định tín dụng vẫn nằm trọn trong tay mô hình và bộ luật nghiệp vụ, còn quyết định phê duyệt cuối cùng thuộc về admin.

### **7.3. Singleton và an toàn đa luồng**

Backend FastAPI phục vụ nhiều request đồng thời trên nhiều luồng, trong khi việc khởi tạo các client LLM, embedding và Qdrant-đặc biệt là nạp mô hình reranker nặng khoảng 1,1 GB-vừa tốn kém vừa tuyệt đối không được phép chạy lặp giữa các luồng. Để giải quyết, mọi tài nguyên dùng chung đều được khởi tạo theo mẫu khóa kiểm tra hai lần (double-checked locking) như minh họa dưới đây:

\_chain\_lock \= Lock()

\_chain \= None

 

def get\_chain():

    global \_chain

    if \_chain is None:                 \# kiểm tra 1 (không khóa, nhanh)

        with \_chain\_lock:              \# chỉ khóa khi cần khởi tạo

            if \_chain is None:         \# kiểm tra 2 (trong khóa, an toàn)

                \_chain \= chat\_prompt | llm | StrOutputParser()

    return \_chain

Kiểm tra ngoài khóa phục vụ đường nóng (đã khởi tạo) mà không cần tranh chấp tài nguyên; khóa chỉ chặn ở lần đầu, và kiểm tra lần hai bên trong khóa đảm bảo đúng một luồng thực hiện khởi tạo. Mẫu này được lặp lại ở get\_retriever và \_get\_classifier\_llm. Reranker đi xa hơn với lazy loading: Reranker.\_ensure\_loaded chỉ thực sự nạp TextCrossEncoder ở lần rerank đầu tiên, nên nếu rerank bị tắt qua config, mô hình 1,1 GB sẽ không bao giờ được tải vào bộ nhớ.

## **8\. Đánh giá chất lượng**

Đánh giá một hệ thống RAG là việc khó, bởi đầu ra của nó là văn bản tự do, không có một đáp án duy nhất để so khớp tuyệt đối như bài toán phân loại. Người ta thường viện tới một LLM khác để chấm điểm, nhưng cách ấy vừa tốn kém, vừa chậm, vừa thiếu tính tái lập do bản thân LLM chấm điểm cũng có yếu tố ngẫu nhiên. CreditIntel chọn một hướng đi khác: xây dựng một khung đánh giá hoàn toàn xác định, không cần LLM chấm điểm, gồm ba module: eval\_metrics.py, eval\_runner.py và eval\_dataset.py. Khung này chạy nhanh, cho kết quả lặp lại được giữa các lần chạy, và đủ nhẹ để nhúng vào quy trình tích hợp liên tục (CI) như một cổng chặn chất lượng.

Nền tảng của khung là bộ dữ liệu đánh giá lưu trong một tệp JSON do eval\_dataset.py quản lý, với ràng buộc cứng là phải có từ 30 đến 50 case. Mỗi case mô tả đầy đủ một tình huống kiểm thử: câu hỏi đầu vào, đáp án tham chiếu (ground\_truth), danh sách nguồn tài liệu kỳ vọng (expected\_sources), các thuật ngữ kỳ vọng xuất hiện trong ngữ cảnh truy xuất (expected\_context\_terms), những cụm bắt buộc phải có trong câu trả lời (must\_include), những cụm cấm tuyệt đối (must\_not\_include), và một nhãn nhóm chủ đề (group) như policy, faq, guardrail, edge\_case hay personalized. Bộ nạp dữ liệu sẽ từ chối những dataset thiếu trường bắt buộc hoặc có id trùng lặp, bảo đảm tính toàn vẹn ngay từ đầu vào.

Trên nền dữ liệu đó, khung tính ba chỉ số. Chỉ số đầu tiên là độ trung thực (Faithfulness), đo xem câu trả lời có thực sự chứa các ý bắt buộc và các ý đó có cơ sở trong ngữ cảnh truy xuất hay hồ sơ khách hàng hay không; cụ thể được tính bằng 0.7 × độ phủ \+ 0.3 × tỷ lệ có cơ sở, rồi trừ đi 0.25 cho mỗi cụm cấm lỡ xuất hiện. Chỉ số thứ hai là độ chính xác ngữ cảnh (Context Precision), bằng tỷ lệ giữa số đoạn truy xuất thực sự liên quan tới nguồn hoặc thuật ngữ kỳ vọng trên tổng số đoạn trả về-đo độ "sạch" của khâu truy xuất. Chỉ số thứ ba là điểm tổng hợp (Overall) của mỗi case, được tính bằng 0.6 × Faithfulness \+ 0.4 × Context Precision; một câu trả lời được coi là đạt khi điểm tổng hợp không thấp hơn ngưỡng PASS\_THRESHOLD là 0.75. Toàn bộ việc khớp cụm từ đều qua hàm normalize\_text để chuẩn hóa dấu câu, hạ chữ thường và gộp khoảng trắng, đồng thời hỗ trợ cú pháp biến thể "phương án A | phương án B" nhằm bám sát sự đa dạng cách diễn đạt tiếng Việt.

Cần thẳng thắn về một giới hạn của khung: nó nghiêng hẳn về phía precision và grounding, còn thành phần recall-tức khả năng truy hồi đủ thông tin liên quan-chỉ hiện diện gián tiếp qua chỉ số độ phủ bên trong Faithfulness. Lý do là độ phủ chỉ có thể đạt cao khi khâu truy xuất đã kéo về đủ tài liệu cần thiết; tuy nhiên đây là một phép đo recall vòng vo chứ không phải recall đúng nghĩa với nhãn "đoạn vàng". Hạn chế này cùng hướng khắc phục được bàn kỹ hơn ở Mục 8.1 và Mục 9\.

Cuối cùng, khung được trang bị cơ chế phát hiện hồi quy dùng trong CI. Hàm diff\_results so sánh kết quả hiện tại với một baseline theo từng id case. Một case bị đánh dấu hồi quy nếu điểm tụt quá ngưỡng CASE\_REGRESSION\_DELTA (−0.15) hoặc rơi từ trạng thái đạt xuống không đạt; cả một lần chạy bị coi là hồi quy khi điểm trung bình toàn cục tụt quá ngưỡng RUN\_REGRESSION\_DELTA (−0.05). Khi runner được gọi với cờ \--fail-on-regression, nó trả về mã thoát khác không trong trường hợp phát hiện hồi quy, cho phép tự động chặn một lần merge nếu bất kỳ thay đổi nào-sửa prompt, đổi thuật toán chunk, hay chỉnh ngưỡng rerank-vô tình làm giảm chất lượng.

### **8.1. Kết quả thực nghiệm** 

Bộ eval 31 case được chạy lại trên pipeline hiện hành (hybrid \+ cross-encoder rerank k=20→12, top\_k=4 parent, LLM gemini-2.5-flash temperature=0.3), trên collection creditintel-kb (76 điểm, đủ vector dense+sparse). Không có case nào lỗi gọi hàm. Kết quả tổng hợp trên toàn bộ 31 case được trình bày trong Bảng 8.1.

***Bảng 8.1. Kết quả đánh giá tổng hợp (31 case)***

| Chỉ số (toàn bộ 31 case) | Giá trị |
| ----- | :---: |
| Faithfulness trung bình | 0.850 |
| Context Precision trung bình | 0.774 |
| Overall trung bình | 0.819 |
| Số case đạt (overall ≥ 0.75) | 23/31 |

Tách theo nhóm chủ đề cho thấy chất lượng phân bố không đều và làm lộ rõ một artifact của thước đo hơn là lỗi pipeline, như trình bày trong Bảng 8.2.

***Bảng 8.2. Kết quả đánh giá phân theo nhóm chủ đề***

| Nhóm | n | Faithfulness | Context Precision | Overall |
| ----- | :---: | :---: | :---: | :---: |
| policy | 5 | 0.953 | 0.950 | 0.952 |
| faq | 10 | 0.930 | 0.975 | 0.948 |
| guardrail | 6 | 0.692 | 1.000 | 0.815 |
| edge\_case | 5 | 0.787 | 0.700 | 0.752 |
| personalized | 5 | 0.837 | 0.000 | 0.502 |

Đọc kết quả, điểm mấu chốt là về nhóm personalized. Năm case personalized "rớt" (overall ≈ 0.50) không phải vì câu trả lời sai, mà vì câu trả lời cá nhân hóa lấy cơ sở (grounding) từ User Context-bốn khối hồ sơ tính sẵn bằng luật cứng (Mục 6.2)-chứ không từ tài liệu KB truy xuất. Trong khi đó, Context Precision chỉ chấm độ sạch của tài liệu KB trả về; với câu hỏi cá nhân, retrieval thường không (và không cần) trả về doc KB nào, nên precision \= 0 theo thiết kế. Faithfulness của nhóm này vẫn cao (0.837), xác nhận nội dung trả lời vẫn đúng. Nếu loại bỏ artifact này (bỏ nhóm personalized khỏi phép đo precision), Context Precision trên 26 case còn lại đạt ≈ 0.92, và tỷ lệ đạt thực chất là 23/26 (\~88%); ba case rớt thật sự là GUARDRAIL-05, EDGE-04 và EDGE-01.

Hệ quả cho khung đo: đây là hạn chế đã biết của metric hiện tại-nó đo precision của retrieval nên trừng phạt oan các câu trả lời grounding-bằng-hồ-sơ. Hướng khắc phục (Mục 9.3): tách một metric "user-context grounding" riêng cho nhóm personalized, thay vì ép chúng vào thước đo precision của KB.

Về Context Recall: khung hiện tại không đo recall trực tiếp do không có nhãn "đoạn vàng" (gold passages) để tính tỷ lệ truy hồi. Recall chỉ hiện diện gián tiếp qua thành phần coverage của Faithfulness. Báo cáo cuối nên nêu rõ giới hạn này hoặc bổ sung một tập gold-passage nhỏ để đo recall đúng nghĩa.

Kiểm tra hồi quy so với mốc 22/05: so với run tốt nhất ngày 22/05 (rerank\_v11\_k24\_top12, overall 0.837), điểm tổng (run temperature=0.3) giảm nhẹ còn 0.819 (Δ \= −0.018), nằm trong dung sai run-level −0.05, không bị gắn cờ hồi quy. Ở mức case có hai ca tụt quá ngưỡng (EDGE-01, GUARDRAIL-06) và ba ca cải thiện (EDGE-03, FAQ-03, FAQ-07).

Để loại dao động do LLM sinh ngẫu nhiên, một run thứ hai được thực hiện ở temperature=0 và so sánh apples-to-apples với baseline cùng nhiệt độ, kết quả trình bày trong Bảng 8.3.

***Bảng 8.3. So sánh kiểm tra hồi quy theo nhiệt độ lấy mẫu***

| So sánh | Overall hiện tại | Overall baseline | Δ | Case hồi quy |
| ----- | :---: | :---: | :---: | ----- |
| temp=0.3 vs 22/05 (rerank tốt nhất) | 0.819 | 0.837 | −0.018 | EDGE-01, GUARDRAIL-06 |
| temp=0 vs 22/05 (temp=0) | 0.824 | 0.831 | −0.007 | chỉ EDGE-01 |

Khi cố định temp=0, chênh lệch tổng co lại còn −0.007 (gần như phẳng) và GUARDRAIL-06 hết hồi quy, xác nhận cú tụt của case này ở run 0.3 chỉ là nhiễu lấy mẫu. Riêng EDGE-01 hồi quy ở cả hai run nên là tín hiệu thật: câu "vay nhiều hơn mức đề xuất?", sau thay đổi retriever.py ngày 02/06, có tập tài liệu trả về đổi thứ tự/thành phần khiến câu trả lời rớt cụm bắt buộc "xét duyệt", kéo Faithfulness 1.0→0.62 và Context Precision 0.75→0.50. Đây là một case lẻ, biên (thiếu đúng một cụm must\_include), đáng theo dõi nhưng không hạ chất lượng tổng thể của pipeline.

Kết luận eval: thay đổi code ngày 02/06 (chain.py/retriever.py) không gây hồi quy ở mức pipeline (Δ overall temp=0 chỉ −0.007). Pipeline hiện hành đạt overall ≈ 0.82, mạnh ở policy/faq (\~0.95), trung bình ở guardrail/edge\_case, và bị thước đo "phạt oan" nhóm personalized như đã phân tích. Một regression case lẻ (EDGE-01) do thay đổi thứ tự retrieval cần được rà soát lại.

Tạo phẩm: rag\_eval\_results\_2026-06-02\_current.json (temp 0.3), rag\_eval\_results\_2026-06-02\_temp0.json (temp 0), và hai file diff tương ứng trong thư mục RAG\_eval/.

## **9\. Điểm mạnh, hạn chế và hướng phát triển**

### **9.1. Điểm mạnh**

Điểm mạnh nổi bật nhất của hệ thống là kiến trúc phòng thủ nhiều tầng. Hai lớp guardrail kẹp ở đầu vào và đầu ra, một system prompt nêu rõ chín quy tắc ứng xử, và triết lý suy giảm duyên dáng thấm vào từng mắt xích của pipeline: khi reranker hỏng thì hệ thống trả về tập ứng viên thô; khi viết lại câu hỏi thất bại thì dùng lại câu gốc; khi truy xuất gặp sự cố thì vẫn trả lời mà không cần tài liệu; khi tóm tắt lỗi thì giữ nguyên bản tóm tắt cũ. Nhờ cách thiết kế đó, không một thành phần phụ trợ đơn lẻ nào có thể kéo sập cả lượt chat-một phẩm chất đặc biệt quan trọng với sản phẩm tài chính cần độ tin cậy cao.

Một thế mạnh cốt lõi khác là cơ chế grounding kép: hệ thống không chỉ dựa vào kho tri thức chính sách mà còn kết hợp với User Context được tính sẵn bằng luật xác định ở tầng Python, qua đó giảm mạnh nguy cơ LLM bịa ra các con số tài chính nhạy cảm. Đi cùng với đó là đường ống truy xuất chất lượng cao, nơi tìm kiếm hybrid bắt được cả ngữ nghĩa lẫn từ khóa chính xác, cross-encoder tinh lọc lại thứ hạng, và kỹ thuật Parent-Child cân bằng giữa độ chính xác khi định vị và độ giàu ngữ cảnh khi sinh câu trả lời. Hệ thống còn vượt khỏi khuôn khổ hỏi-đáp nhờ công cụ điều chỉnh khoản vay biết gọi lại chính mô hình ML production, biến trợ lý thành một tác nhân biết hành động kèm vòng xác nhận an toàn. Toàn bộ chất lượng đó được bảo chứng bằng một khung đánh giá xác định, tái lập được và có khả năng chặn hồi quy ngay trong CI.

### **9.2. Hạn chế**

Song hành với các thế mạnh là những hạn chế cần nhìn nhận thẳng thắn. Trước hết là độ trễ của khâu xếp hạng lại: cross-encoder chạy trên CPU mất khoảng 3-10 giây với cache đã ấm, và đây chính là nút cổ chai độ trễ chính của cả pipeline; thêm vào đó, lần khởi động đầu tiên sau khi bật tính năng còn phải tải về mô hình nặng khoảng 1,1 GB (qua bước pre-warm ở startup của main.py). Kế đến, router phân loại ý định dựa trên regex tuy nhanh và rẻ nhưng bản chất giòn: đường tắt bằng từ khóa dễ bỏ sót những cách diễn đạt lạ, và khi đó hệ thống buộc phải rơi xuống lời gọi LLM, làm tăng cả độ trễ lẫn chi phí.

Về mặt nội dung, kho tri thức hiện còn nhỏ, mới chỉ gồm policy.md, faq.md và từ điển dữ liệu, nên chưa phủ hết các tình huống nghiệp vụ phức tạp; chất lượng câu trả lời vì thế bị chặn trên bởi độ phủ của kho. Tương tự, việc phát hiện ý định điều chỉnh khoản vay vẫn dựa vào một danh sách cụm từ tiếng Việt phải bảo trì thủ công, khó tổng quát hóa cho những cách hỏi ngoài dự liệu. Hệ thống cũng phụ thuộc vào nhà cung cấp bên ngoài khi cả LLM lẫn embedding đều đi qua OpenRouter, kéo theo rủi ro về độ trễ, chi phí và tính sẵn sàng của bên thứ ba. Cuối cùng, ngay bản thân thước đo đánh giá cũng còn thiên lệch: Context Precision đo độ sạch của tài liệu KB nên chấm oan điểm không cho nhóm câu trả lời cá nhân hóa (vốn lấy cơ sở từ User Context chứ không từ KB), đồng thời khung chưa đo được Context Recall một cách trực tiếp do thiếu tập "đoạn vàng" tham chiếu.

### **9.3. Hướng phát triển**

Từ những hạn chế trên, một số hướng phát triển hiện ra khá rõ ràng. Về hiệu năng, nút cổ chai rerank có thể được giải quyết bằng cách đưa cross-encoder lên GPU, thay bằng một reranker nhẹ hơn hoặc đã lượng tử hóa, hay xếp hạng lại theo cơ chế bất đồng bộ kèm một ngưỡng tin cậy để bỏ qua bước này khi không thực sự cần thiết. Về tri thức, kho cần được mở rộng và tự động hóa: bổ sung các kịch bản nghiệp vụ, đồng bộ định kỳ với chính sách thực tế, và thêm cơ chế quản lý phiên bản cho tài liệu. Về định tuyến, lớp regex giòn có thể được thay thế hoặc bổ trợ bằng một bộ phân loại học máy nhẹ được huấn luyện riêng, qua đó giảm bớt sự phụ thuộc vào LLM cho việc phân loại ý định.

Trên trục tác nhân, bộ công cụ có thể được mở rộng vượt khỏi việc điều chỉnh khoản vay, bổ sung các công cụ tra cứu trạng thái đơn, ước tính lịch trả nợ, hay mô phỏng kịch bản "nếu-thì" cho điểm tín dụng. Riêng về đánh giá, hai cải tiến đáng ưu tiên là: (1) tách một chỉ số "user-context grounding" riêng cho nhóm cá nhân hóa thay vì ép chúng vào thước đo precision của KB, đồng thời bổ sung một tập "đoạn vàng" để đo Context Recall đúng nghĩa; (2) thêm một tầng chấm điểm bằng LLM-as-judge chạy cạnh khung xác định hiện tại để bắt những lỗi ngữ nghĩa mà phép khớp cụm từ bỏ sót. Sau cùng, về phương diện vận hành, các bộ đếm sẵn có như get\_rerank\_stats và tỷ lệ rơi vào nhánh dự phòng nên được đưa lên dashboard quản trị, giúp phát hiện sớm những suy giảm âm thầm của pipeline trước khi chúng ảnh hưởng tới người dùng.

[image1]: <data:image/png;base64,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>
import { useState } from "react";
import FileUploader from "../components/FileUploader";
import { uploadDocument } from "../api/documentApi";

// 업로드 페이지
const UploadPage = () => {
    const [loading, setLoading] = useState(false);  
    const [error, setError] = useState(null);
    const [result, setResult] = useState(null);

    // 파일 업로드 시 호출  
    const handleUpload = async (file) => {
      try {
        setLoading(true);
        setError(null);
        setResult(null);

        const data = await uploadDocument(file);
        setResult(data);
        alert("업로드했습니다.")
      } catch(e){
        setError(e.message || "업로드 중 오류가 발생했습니다.");
      } finally{
        setLoading(false);
      }
      // TODO: backend API 연동
    };





    return (
        <div style={{ maxWidth: 720, margin: "40px auto", padding: 16 }}>
          <h1 style={{ marginBottom: 8 }}>Sift</h1>
          <p style={{ marginTop: 0, opacity: 0.8 }}>
            문서를 업로드하면 핵심 내용을 요약해드립니다.
          </p>

          <FileUploader onSubmit={handleUpload} />

          {loading && <p style={{ marginTop: 12 }}>업로드 중...</p>}
          {error && <p style={{ marginTop: 12, color: "crimson" }}>{error}</p>}

          {result && (
            <div style={{ marginTop: 16 }}>
              <h3>업로드 결과</h3>
              <pre
                style={{
                  background: "#111",
                  color: "#eee",
                  padding: 12,
                  borderRadius: 8,
                  overflowX: "auto",
                }}
              >
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
    );
};

export default UploadPage;

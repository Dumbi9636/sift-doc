import { useState } from "react";
import FileUploader from "../components/FileUploader";
import { uploadDocument } from "../api/documentApi";

const UploadPage = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // 파일 업로드 시 호출
  const handleUpload = async ({ file, model, mode, maxChars, numPredict }) => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await uploadDocument({ file, model, mode, maxChars, numPredict });
      setResult(data);
    } catch (e) {
      setError(e.message || "업로드 중 오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", padding: 16 }}>
      <h1 style={{ marginBottom: 8 }}>Sift</h1>
      <p style={{ marginTop: 0, opacity: 0.8 }}>
        텍스트 문서를 업로드하면 핵심 내용을 요약해드립니다.
      </p>

      <FileUploader onSubmit={handleUpload} />

      {loading && <p style={{ marginTop: 12 }}>요약 중...</p>}
      {error && <p style={{ marginTop: 12, color: "crimson" }}>{error}</p>}

        {result?.summarize?.summary && (
        <div style={{ marginTop: 16 }}>
          <h3>요약 결과</h3>

          <ul
            style={{
              background: "#111",
              color: "#eee",
              padding: 12,
              borderRadius: 8,
              margin: 0,
              lineHeight: 1.6,
              listStylePosition: "inside",
            }}
          >
            {result.summarize.summary
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
              .map((line, idx) => {
                // "- "로 시작하면 제거해서 깔끔하게 표시
                const text = line.startsWith("- ") ? line.slice(2) : line;
                return <li key={idx}>{text}</li>;
              })}
          </ul>
        </div>
      )}
    </div>
  );
};

export default UploadPage;

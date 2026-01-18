import { useState } from "react";
import FileUploader from "../components/FileUploader";

// 업로드 페이지
const UploadPage = () => {
    const [loading, setLoading] = useState(false);  
    const [error, SetError] = useState(null);

    // 파일 업로드 시 호출  
    const handleUpload = async (file) => {
      try {
        setLoading(true);
        SetError(null);

        const result = await uploadDocument(file);
        console.log("업로드 결과:", result);
        alert("업로드했습니다.")
      } catch(e){
        SetError(e.message);
      } finally{
        setLoading(false);
      }
      // TODO: backend API 연동
    };





    return (
        <div>
            <h1>Sift</h1>
            <hr />
            <p>문서를 업로드하면 핵심 내용을 요약해드립니다.</p>
            
            <FileUploader onSubmit={handleUpload} />

            {loading && <p>업로드 중...</p>}
            {error && <p style={{color: "red" }}>{error}</p>}
        </div>
    );
};

export default UploadPage;

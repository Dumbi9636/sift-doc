import { useState } from "react";

const FileUploader = ({ onSubmit }) => {
  const [file, setFile] = useState(null);

  const handleChange = (e) => setFile(e.target.files?.[0] ?? null);

  const handleSubmit = () => {
    if (!file) {
      alert("파일을 선택하세요.");
      return;
    }
    onSubmit(file);
  };

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <input type="file" onChange={handleChange} />
      <button onClick={handleSubmit}>업로드</button>
    </div>
  );
};

export default FileUploader;

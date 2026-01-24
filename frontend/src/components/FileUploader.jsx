import { useState } from "react";

const FileUploader = ({ onSubmit }) => {
  const [file, setFile] = useState(null);
  const [model, setModel] = useState("gemma3:4b");
  const [mode, setMode] = useState("news");
  const [maxChars, setMaxChars] = useState(1200);
  const [numPredict, setNumPredict] = useState(260);

  const handleSubmit = () => {
    if (!file) return alert("파일을 선택하세요.");
    onSubmit({ file, model, mode, maxChars, numPredict });
  };

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <input type="file" accept=".txt" onChange={(e)=>setFile(e.target.files?.[0] ?? null)} />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <label>
          model
          <input value={model} onChange={(e)=>setModel(e.target.value)} />
        </label>

        <label>
          mode
          <select value={mode} onChange={(e)=>setMode(e.target.value)}>
            <option value="news">news</option>
            <option value="default">default</option>
            <option value="report">report</option>
          </select>
        </label>

        <label>
          max_chars
          <input type="number" value={maxChars} onChange={(e)=>setMaxChars(Number(e.target.value))} />
        </label>

        <label>
          num_predict
          <input type="number" value={numPredict} onChange={(e)=>setNumPredict(Number(e.target.value))} />
        </label>
      </div>

      <button onClick={handleSubmit}>요약 실행</button>
    </div>
  );
};

export default FileUploader;

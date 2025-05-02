import axios from "axios";

export default function Download() {
  const handleDownload = async () => {
    const response = await axios.get("/api/download", { responseType: "blob" });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "telegram_bot.zip");
    document.body.appendChild(link);
    link.click();
  };

  return (
    <div className="container text-center mt-5">
      <h1 className="mb-4">Скачать Бота</h1>
      <button onClick={handleDownload} className="btn btn-success">
        Скачать ZIP
      </button>
    </div>
  );
}

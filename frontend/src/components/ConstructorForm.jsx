import { useState } from "react";
import axios from "axios";

export default function ConstructorForm() {
  const [startMessage, setStartMessage] = useState({ text: "", photo: null });
  const [questions, setQuestions] = useState([]);

  const addQuestion = () => {
    const newId = questions.length > 0 ? Math.max(...questions.map(q => q.id)) + 1 : 1;
    setQuestions([...questions, { id: newId, text: "", options: [""], branches: {}, mediaFile: null }]);
  };

  const handleQuestionChange = (index, value) => {
    const updated = [...questions];
    updated[index].text = value;
    setQuestions(updated);
  };

  const handleOptionChange = (qIndex, oIndex, value) => {
    const updated = [...questions];
    updated[qIndex].options[oIndex] = value;
    setQuestions(updated);
  };

  const handleBranchChange = (qIndex, optionValue, nextId) => {
    const updated = [...questions];
    updated[qIndex].branches[optionValue] = Number(nextId);
    setQuestions(updated);
  };

  const handleMediaChange = (index, file) => {
    const updated = [...questions];
    updated[index].mediaFile = file;
    setQuestions(updated);
  };

  const handleStartPhotoChange = (file) => {
    setStartMessage(prev => ({ ...prev, photo: file }));
  };

  const addOption = (qIndex) => {
    const updated = [...questions];
    updated[qIndex].options.push("");
    setQuestions(updated);
  };

  const handleSubmit = async () => {
    try {
      // Шаг 1: отправляем проект
      const content = {
        start_message: {
          text: startMessage.text,
          photo: startMessage.photo ? startMessage.photo.name : ""
        },
        questions: questions.map(q => {
          const question = {
            id: q.id,
            text: q.text,
            options: q.options
          };
          if (q.branches && Object.keys(q.branches).length > 0) {
            question.branches = q.branches;
          }
          if (q.mediaFile) {
            if (q.mediaFile.name.endsWith(".gif")) question.gif = q.mediaFile.name;
            else question.photo = q.mediaFile.name;
          }
          return question;
        })
      };

      const formData = new FormData();
      formData.append("project", JSON.stringify({
        name: "Опросник",
        template_type: "quiz",
        description: "Опросник для тестирования",
        token: "your-bot-token-here",
        content: content
      }));

      const projectResponse = await axios.post("/api/projects", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });

      const projectId = projectResponse.data.project_id;

      // Шаг 2: загружаем все файлы
      const filesData = new FormData();

      if (startMessage.photo) {
        filesData.append("files", startMessage.photo);
      }
      questions.forEach(q => {
        if (q.mediaFile) {
          filesData.append("files", q.mediaFile);
        }
      });

      if (Array.from(filesData).length > 0) {
        await axios.post(`/api/projects/${projectId}/media`, filesData, {
          headers: { "Content-Type": "multipart/form-data" }
        });
      }

      alert("Бот успешно создан и файлы загружены!");
    } catch (error) {
      console.error(error);
      alert("Ошибка при создании бота");
    }
  };

  return (
    <div className="container mt-5">
      <h1 className="mb-4">Конструктор Опросника</h1>

      <div className="card p-3 mb-4">
        <h5>Стартовое сообщение</h5>
        <input
          type="text"
          placeholder="Текст старта"
          className="form-control mb-2"
          value={startMessage.text}
          onChange={(e) => setStartMessage({ ...startMessage, text: e.target.value })}
        />
        <input
          type="file"
          accept="image/*,image/gif"
          className="form-control mb-2"
          onChange={(e) => {
            const file = e.target.files[0];
            if (file) handleStartPhotoChange(file);
          }}
        />
        {startMessage.photo && (
          <img src={URL.createObjectURL(startMessage.photo)} alt="Preview" style={{ maxWidth: "200px", maxHeight: "200px" }} className="mt-2" />
        )}
      </div>

      {questions.map((question, qIndex) => (
        <div key={qIndex} className="card p-3 mb-3">
          <h5>Вопрос #{question.id}</h5>
          <input
            type="text"
            placeholder="Текст вопроса"
            className="form-control mb-2"
            value={question.text}
            onChange={(e) => handleQuestionChange(qIndex, e.target.value)}
          />

          {question.options.map((option, oIndex) => (
            <div key={oIndex} className="input-group mb-2">
              <input
                type="text"
                className="form-control"
                placeholder={`Вариант ${oIndex + 1}`}
                value={option}
                onChange={(e) => handleOptionChange(qIndex, oIndex, e.target.value)}
              />
              <input
                type="number"
                className="form-control"
                placeholder="ID следующего вопроса"
                onChange={(e) => handleBranchChange(qIndex, option, e.target.value)}
              />
            </div>
          ))}

          <button onClick={() => addOption(qIndex)} className="btn btn-outline-primary btn-sm mb-2">
            Добавить вариант ответа
          </button>

          <input
            type="file"
            accept="image/*,image/gif"
            className="form-control mb-2"
            onChange={(e) => {
              const file = e.target.files[0];
              if (file) handleMediaChange(qIndex, file);
            }}
          />

          {question.mediaFile && (
            <img src={URL.createObjectURL(question.mediaFile)} alt="Preview" style={{ maxWidth: "200px", maxHeight: "200px" }} className="mt-2" />
          )}
        </div>
      ))}

      <div className="d-flex gap-3">
        <button onClick={addQuestion} className="btn btn-secondary">
          Добавить вопрос
        </button>
        <button onClick={handleSubmit} className="btn btn-success">
          Создать Бота
        </button>
      </div>
    </div>
  );
}

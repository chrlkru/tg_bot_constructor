// import { Link } from "react-router-dom";

// export default function Home() {
//   return (
//     <div className="container text-center mt-5">
//       <h1 className="mb-4">Конструктор Telegram-ботов</h1>
//       <Link to="/constructor" className="btn btn-primary">
//         Создать Опросник
//       </Link>
//     </div>
//   );
// }
import React from "react";
import "../styles/Home.css";

export default function Home() {
  return (
    <div className="main-page">
      {/* Верхняя секция */}
      <div className="hero-section">
        <div className="hero-text">
          <h1>КОНСТРУКТОР ЧАТ-БОТОВ В TELEGRAM</h1>
          <p>
            Создавайте чат-боты в Telegram без навыков программирования. Подходит для любого бизнеса.
          </p>
          <button className="create-bot-button">Создать чат-бот</button>
        </div>
        <div className="hero-image">
          <img src="/phone.png" alt="Phone preview" />
        </div>
      </div>

      {/* Секция преимуществ */}
      <div className="advantages-section">
        <h2>РЕШАЙТЕ БИЗНЕС-ЗАДАЧИ С ПОМОЩЬЮ ЧАТ-БОТОВ</h2>

        <div className="advantages-grid">
          {advantages.map((item, index) => (
            <div key={index} className="advantage-card">
              <div className="plus-sign">+</div>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const advantages = [
  {
    title: "Рост продаж и среднего чека",
    text: "Настройте сценарии, которые помогут клиентам принять решение о покупке",
  },
  {
    title: "Автоматизация процессов",
    text: "Заполните бот полезным контентом, чтобы пользователи меньше обращались в службу поддержки",
  },
  {
    title: "На связи в режиме 24/7",
    text: "Ваши клиенты смогут получить дополнительную информацию в любое время",
  },
  {
    title: "Забота о клиентах",
    text: "Общайтесь с вашей аудиторией там, где ей это удобно",
  },
];

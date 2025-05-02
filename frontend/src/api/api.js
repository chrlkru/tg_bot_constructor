import axios from "axios";

export const createBot = (questions) => {
  return axios.post("/api/create_bot", { questions });
};

export const downloadBot = () => {
  return axios.get("/api/download", { responseType: "blob" });
};

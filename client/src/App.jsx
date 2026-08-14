import { Route, Routes } from 'react-router-dom'
import Header from './components/Header.jsx'
import DetallePage from './pages/DetallePage.jsx'
import HomePage from './pages/HomePage.jsx'
import NuevaPage from './pages/NuevaPage.jsx'
import AutorizadosPage from './pages/AutorizadosPage.jsx'
import EliminadasPage from './pages/EliminadasPage.jsx'

export default function App() {
  return (
    <div className="layout">
      <Header />
      <main className="main">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/nueva" element={<NuevaPage />} />
          <Route path="/solicitudes/:id" element={<DetallePage />} />
          <Route path="/autorizados" element={<AutorizadosPage />} />
          <Route path="/eliminadas" element={<EliminadasPage />} />
        </Routes>
      </main>
    </div>
  )
}

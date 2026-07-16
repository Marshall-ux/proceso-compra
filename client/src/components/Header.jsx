import { NavLink } from 'react-router-dom'
import bannerNeostar from '../assets/header-neostar.png'

export default function Header() {
  const clase = ({ isActive }) => (isActive ? 'navlink navlink--active' : 'navlink')
  return (
    <header className="header">
      <div className="header__bar">
        <NavLink to="/">
          <img src={bannerNeostar} alt="Neostar" className="header__banner" />
        </NavLink>
        <nav className="header__nav">
          <NavLink to="/" end className={clase}>Solicitudes</NavLink>
          <NavLink to="/nueva" className={clase}>Nueva</NavLink>
          <NavLink to="/autorizados" className={clase}>Autorizados</NavLink>
        </nav>
      </div>
    </header>
  )
}

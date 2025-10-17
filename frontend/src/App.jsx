import './App.css'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import Login from './pages/Login'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Device from './pages/Device'
import SiteScreen from './pages/Site'
import SiteDeviceScreen from './pages/SiteDevice'

function App() {

  return (
    <BrowserRouter>
      <Routes>
        <Route path='/' element={<Home />} />
        <Route path='/login' element={<Login />} />
        <Route path='/dashboard' element={<Dashboard />} />
        <Route path='/device' element={<Device />} />
        <Route path='/site' element={<SiteScreen />} />
        <Route path='/site/:deviceId' element={<SiteDeviceScreen />} />

        {/* <Route path='*' element={<NotFound />} /> */}
      </Routes>
    </BrowserRouter>
  )
}

export default App

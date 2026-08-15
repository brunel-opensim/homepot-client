import { useEffect } from 'react';

export default function useSessionMessage(location, setSessionMsg) {
  useEffect(() => {
    if (location.state?.message) {
      setSessionMsg(location.state.message);
      const timer = setTimeout(() => setSessionMsg(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [location, setSessionMsg]);
}

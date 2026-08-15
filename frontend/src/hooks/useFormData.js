import { useState } from 'react';

export default function useFormData(initialValues) {
  const [formData, setFormData] = useState(initialValues);
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };
  return [formData, setFormData, handleChange];
}

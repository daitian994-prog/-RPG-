export default function InkButton({ children, onClick, disabled, variant = 'primary', className = '' }) {
  return <button onClick={onClick} disabled={disabled} className={`ink-button ${variant} ${className}`}>{children}</button>
}


import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Intervention, PaymentPinModal } from './App'

const transaction = {
  id: 'demo-id',
  recipient_account_id: '8091234567',
  risk_score: 0.92,
  risk_tier: 'critical',
  risk_reason: 'Three users reported this beneficiary account',
  network_report_count: 3,
  reflection_prompt: 'In your own words, what is this payment for?',
  reflection_answer: '',
  reflection_red_flags: [],
  reflection_submitted_at: null,
  cooldown_until: new Date(Date.now() + 30_000).toISOString(),
}

describe('flagged transaction intervention', () => {
  it('requires reflection before continuing and exposes the network signal', () => {
    render(<Intervention transaction={transaction} onTransaction={vi.fn()} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('heading', { name: transaction.reflection_prompt })).toBeInTheDocument()
    expect(screen.getByText(/3 other Eso users reported/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /request security review/i })).toBeDisabled()
  })
})

describe('payment PIN modal', () => {
  it('collects four separate digits and submits one PIN value', () => {
    const confirm = vi.fn()
    render(<MemoryRouter><PaymentPinModal onClose={vi.fn()} onConfirm={confirm} /></MemoryRouter>)
    const inputs = [1, 2, 3, 4].map((number) => screen.getByLabelText(`Payment PIN digit ${number}`))
    ;['2', '5', '8', '0'].forEach((digit, index) => fireEvent.change(inputs[index], { target: { value: digit } }))
    fireEvent.click(screen.getByRole('button', { name: /authorize and analyse/i }))
    expect(confirm).toHaveBeenCalledWith('2580')
  })
})

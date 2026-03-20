import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { ProposalResponse } from '../types'
import { ProposalCard } from './ProposalCard'

const baseProposal: ProposalResponse = {
  type: 'proposal',
  proposal_id: 'test-proposal-42',
  message: 'Testvorschlag',
  steps: [
    { step_type: 'load_csv', parameters_summary: 'source=bike.csv' },
    { step_type: 'impute_missing' },
    { step_type: 'train_test_split', parameters_summary: 'test_size=0.2' },
  ],
}

describe('ProposalCard', () => {
  it('rendert Label „Vorschlag (noch nicht ausgeführt)"', () => {
    render(<ProposalCard proposal={baseProposal} onConfirm={vi.fn()} />)
    expect(
      screen.getByText('Vorschlag (noch nicht ausgeführt)'),
    ).toBeInTheDocument()
  })

  it('rendert alle Steps mit step_type', () => {
    render(<ProposalCard proposal={baseProposal} onConfirm={vi.fn()} />)
    expect(screen.getByText('load_csv')).toBeInTheDocument()
    expect(screen.getByText('impute_missing')).toBeInTheDocument()
    expect(screen.getByText('train_test_split')).toBeInTheDocument()
  })

  it('rendert parameters_summary wenn vorhanden', () => {
    render(<ProposalCard proposal={baseProposal} onConfirm={vi.fn()} />)
    expect(screen.getByText(/source=bike\.csv/)).toBeInTheDocument()
    expect(screen.getByText(/test_size=0\.2/)).toBeInTheDocument()
  })

  it('rendert keinen Parameters-Text wenn parameters_summary fehlt', () => {
    render(<ProposalCard proposal={baseProposal} onConfirm={vi.fn()} />)
    // impute_missing hat kein parameters_summary — kein "—" neben dem Step
    const items = screen.getAllByRole('listitem')
    const imputeItem = items.find((el) => el.textContent?.includes('impute_missing'))
    expect(imputeItem?.textContent?.trim()).toBe('impute_missing')
  })

  it('rendert Button „Bestätigen & Ausführen"', () => {
    render(<ProposalCard proposal={baseProposal} onConfirm={vi.fn()} />)
    expect(
      screen.getByRole('button', { name: /Bestätigen & Ausführen/i }),
    ).toBeInTheDocument()
  })

  it('Button-Click ruft onConfirm mit proposal_id auf', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(<ProposalCard proposal={baseProposal} onConfirm={onConfirm} />)

    await user.click(screen.getByRole('button', { name: /Bestätigen/i }))

    expect(onConfirm).toHaveBeenCalledOnce()
    expect(onConfirm).toHaveBeenCalledWith('test-proposal-42')
  })

  it('Button-Click ruft onConfirm mit leerem String wenn proposal_id undefined', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    const proposalWithoutId: ProposalResponse = {
      type: 'proposal',
      message: 'Kein ID',
      steps: [],
    }
    render(<ProposalCard proposal={proposalWithoutId} onConfirm={onConfirm} />)

    await user.click(screen.getByRole('button', { name: /Bestätigen/i }))

    expect(onConfirm).toHaveBeenCalledWith('')
  })

  it('Sonderzeichen in step_type werden als Text gerendert (kein XSS)', () => {
    const xssProposal: ProposalResponse = {
      type: 'proposal',
      proposal_id: 'xss-test',
      message: '<script>alert(1)</script>',
      steps: [
        {
          step_type: '<img src=x onerror=alert(1)>',
          parameters_summary: '<b>bold</b>',
        },
      ],
    }
    render(<ProposalCard proposal={xssProposal} onConfirm={vi.fn()} />)

    // Der Inhalt muss als Text sichtbar sein, nicht als HTML geparst
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument()
    expect(screen.getByText(/<b>bold<\/b>/)).toBeInTheDocument()

    // Kein <script>-Element im DOM
    expect(document.querySelector('script')).toBeNull()
    // kein <img> durch XSS eingefügt
    expect(document.querySelector('img')).toBeNull()
  })

  it('Button ist klickbar wenn disabled falsy (undefined)', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(<ProposalCard proposal={baseProposal} onConfirm={onConfirm} />)

    const btn = screen.getByRole('button', { name: /Bestätigen/i })
    expect(btn).not.toBeDisabled()

    await user.click(btn)
    expect(onConfirm).toHaveBeenCalledOnce()
  })

  it('Button hat disabled-Attribut wenn disabled=true', () => {
    render(<ProposalCard proposal={baseProposal} onConfirm={vi.fn()} disabled={true} />)
    expect(screen.getByRole('button', { name: /Bestätigen/i })).toBeDisabled()
  })

  it('onConfirm wird bei disabled=true nicht aufgerufen', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(<ProposalCard proposal={baseProposal} onConfirm={onConfirm} disabled={true} />)

    await user.click(screen.getByRole('button', { name: /Bestätigen/i }))
    expect(onConfirm).not.toHaveBeenCalled()
  })
})

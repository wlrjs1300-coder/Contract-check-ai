const STEPS = ['파일 선택', '조항 확인', '분석 실행', '결과 확인'] as const

type AnalysisStepperProps = Readonly<{
  currentStep: 1 | 2 | 3 | 4
  completedThrough: 0 | 1 | 2 | 3 | 4
}>

export function AnalysisStepper({ currentStep, completedThrough }: AnalysisStepperProps) {
  return (
    <nav className="stepper" aria-label="분석 진행 단계">
      <ol>
        {STEPS.map((label, index) => {
          const step = (index + 1) as 1 | 2 | 3 | 4
          const complete = step <= completedThrough
          const current = !complete && step === currentStep
          const state = complete ? '완료' : current ? '현재 단계' : '예정'
          return (
            <li
              className={complete ? 'is-complete' : current ? 'is-current' : undefined}
              aria-current={current ? 'step' : undefined}
              aria-label={`${step}단계 ${label}: ${state}`}
              key={label}
            >
              <span>{String(step).padStart(2, '0')}</span>
              <strong>{label}</strong>
              <small>{state}</small>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

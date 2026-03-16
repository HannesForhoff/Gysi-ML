import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { expect } from 'vitest'
import * as matchers from '@testing-library/jest-dom/matchers'

expect.extend(matchers)

afterEach(() => {
	cleanup()
})

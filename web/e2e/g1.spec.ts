import { expect, test } from '@playwright/test'

const MOCK_ANSWER =
  'Đây là phản hồi mô phỏng cho câu hỏi của bạn. Nội dung này chỉ dùng để kiểm thử kỹ thuật G1, không phải tư vấn hành chính.'

test('complete browser flow keeps history and isolates a second user', async ({ page }) => {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  const userA = `e2e-a-${suffix}`
  const userB = `e2e-b-${suffix}`
  const question = 'D0_SYSTEM_SMOKE: kiểm tra giao diện G1.'

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Trợ lý hành chính' })).toBeVisible()

  await page.getByLabel('Tên hiển thị').fill(userA)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByText(userA, { exact: true })).toBeVisible()

  await page.locator('button.new-conversation').click()
  await expect(page.getByRole('heading', { name: 'Cuộc trò chuyện mới' })).toBeVisible()
  await page.getByPlaceholder('Viết tin nhắn kiểm thử...').fill(question)
  await page.getByRole('button', { name: 'Gửi' }).click()

  await expect(page.getByText(question, { exact: true })).toBeVisible()
  await expect(page.getByText(MOCK_ANSWER, { exact: true })).toBeVisible({ timeout: 15_000 })

  await page.reload()
  await expect(page.getByText(question, { exact: true })).toBeVisible()
  await expect(page.getByText(MOCK_ANSWER, { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Đăng xuất' }).click()
  await expect(page.getByRole('heading', { name: 'Trợ lý hành chính' })).toBeVisible()

  await page.getByLabel('Tên hiển thị').fill(userB)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByText('Chưa có cuộc trò chuyện nào.')).toBeVisible()
  await expect(page.getByText(question, { exact: true })).toHaveCount(0)
})

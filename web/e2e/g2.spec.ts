import { expect, test } from '@playwright/test'

test.skip(process.env.G2_E2E !== '1', 'Runs only against the offline G2 Compose overlay')

test('grounded answer renders a safe source and survives reload', async ({ page }) => {
  const user = `g2-e2e-${Date.now()}-${Math.random().toString(16).slice(2)}`
  const question = 'khai sinh sao mai'

  await page.goto('/')
  await page.getByLabel('Tên hiển thị').fill(user)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await page.locator('button.new-conversation').click()
  await page.getByPlaceholder('Viết tin nhắn kiểm thử...').fill(question)
  await page.getByRole('button', { name: 'Gửi' }).click()

  await expect(page.getByText('Đã đối chiếu nguồn')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(/BẢN MÔ PHỎNG D0/)).toBeVisible()
  await expect(page.getByText(/Dữ liệu mô phỏng D0/)).toBeVisible()
  const source = page.getByRole('link', { name: /Đăng ký khai sinh Sao Mai/ })
  await expect(source).toHaveAttribute('href', 'https://fixture.invalid/d0/birth_star')

  await page.reload()
  await expect(page.getByText('Đã đối chiếu nguồn')).toBeVisible()
  await expect(page.getByRole('link', { name: /Đăng ký khai sinh Sao Mai/ })).toBeVisible()
})

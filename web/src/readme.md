# G1 Web - Huong dan su dung

Tai lieu nay danh cho phan Frontend cua Giai doan 1. Frontend dung React + TypeScript + Vite va giao tiep voi Core Backend qua Public API.

## 1. Cach chay server local

### Yeu cau

- Node.js va npm.
- Thu muc project: `c:\Users\ADMIN\g1-app`.
- Core Backend chay tai `http://localhost:8000` neu test backend that.

### Cai dat va chay Frontend

Mo PowerShell tai thu muc project, khong phai thu muc `src`:

```powershell
cd c:\Users\ADMIN\g1-app
npm install
npm run dev
```

Sau do mo URL Vite hien trong terminal, thong thuong la `http://localhost:5173`. Contract G1 quy uoc Web la port `3000`; neu can dung dung port nay, chay `npm run dev -- --port 3000`.

Neu can kiem tra truoc khi ban giao:

```powershell
npm run build
npm run lint
```

Sau khi sua `.env`, phai restart Vite de bien moi truong duoc nap lai.

### Cau hinh moi truong

File `.env.example` la mau cau hinh:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_ENABLE_LOCAL_ADMIN_BYPASS=false
```

File `.env` dung cho may local va khong duoc dua secret vao source code.

## 2. Luu y ve Backend

### Luong he thong

```text
React Web :5173
		-> Core Backend :8000
				-> PostgreSQL
				-> AI Service Mock :8001
```

Web khong duoc goi truc tiep AI Service. Moi request di qua Core Backend bang `VITE_API_BASE_URL` va request xac thuc phai dung `credentials: "include"`.

### Public API Frontend dang su dung

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
GET  /api/v1/conversations
POST /api/v1/conversations
GET  /api/v1/conversations/{conversation_id}/messages
POST /api/v1/conversations/{conversation_id}/messages
```

Login gui:

```json
{
	"display_name": "Tú"
}
```

Gui message gui:

```json
{
	"client_message_id": "uuid",
	"content": "Noi dung tin nhan"
}
```

Backend can dam bao:

- Tao session cookie `HttpOnly`, `SameSite=Lax`.
- Khong tin `user_id` tu Frontend.
- Moi conversation/message deu kiem tra ownership.
- Retry cung `client_message_id` khong tao duplicate user message.
- Luu user message truoc khi goi AI Service.
- AI timeout/error khong lam mat user message.
- Error response co `code`, `message` va `request_id`.

Hien tai Frontend da co API client, nhung Core Backend/PostgreSQL/AI Service chua nam trong project nay. Khi port `8000` chua chay, login backend se that bai va giao dien hien thong bao loi ket noi.

## 3. Che do local admin de test giao dien

De test UI truoc khi Backend xong, dat trong `.env`:

```env
VITE_ENABLE_LOCAL_ADMIN_BYPASS=true
```

Khi che do nay bat:

- Chi ten `admin` va `admin2` duoc bypass Backend.
- `admin` va `admin2` co hai kho conversation/message rieng trong `localStorage` de test user isolation co ban.
- Refresh van thay history local.
- Khong co session cookie va khong co du lieu PostgreSQL.
- Ten khac van goi Core Backend binh thuong.

Day chi la che do development. Neu deploy voi flag `true`, bat ky ai truy cap Frontend cung co the nhap `admin` de vao local mode.

Khi test Backend that, bat buoc dat:

```env
VITE_ENABLE_LOCAL_ADMIN_BYPASS=false
```

Sau do restart Vite.

## 4. Chi tiet cac trang thai tren giao dien

- `Loading`: hien thi khi app dang kiem tra session ban dau. Trong luc nay chua cho thao tac login.
- `Empty`: hien thi khi chua co conversation, chua chon conversation, hoac conversation chua co message.
- `Unauthorized`: hien thi khi Backend tra `401`, bao gom session het han hoac chua dang nhap. Nguoi dung duoc dua ve login.
- `API error`: hien thi khi Backend tra loi loi khac, sai response, thieu URL API hoac khong ket noi duoc backend.
- `AI timeout`: hien thi khi Backend tra `408`, `504`, ma loi `AI_SERVICE_TIMEOUT` hoac thong diep timeout. Noi dung draft duoc giu lai.
- `Retry`: nut `Thu lai` gui lai cung `client_message_id`, tranh tao duplicate user message.

Trong local admin mode, AI response la response local de test UI; cac trang thai loi AI that chi xac minh duoc khi tat bypass va noi voi Backend.

## 5. Checklist test Frontend

### Test thu cong voi local admin

- Mo trang va thay man hinh login.
- Nhap `admin` va vao duoc workspace.
- Tao conversation moi.
- Gui message va thay user/assistant message.
- Refresh va kiem tra history van con.
- Logout va kiem tra quay ve man hinh login.
- Nhap ten khac de kiem tra request di qua Backend.

### Test voi Backend that

- Dat `VITE_ENABLE_LOCAL_ADMIN_BYPASS=false`.
- Login thanh cong va nhan session cookie.
- Tai conversation list tu API.
- Tao conversation trong database.
- Gui message va nhan Mock AI response.
- Refresh de tai history tu PostgreSQL.
- AI error/timeout hien loi va cho retry.
- Retry khong tao duplicate user message.
- Logout lam session Backend het hieu luc.

### Automated test can bo sung

Frontend chua co Vitest/React Testing Library. Khi them test, uu tien:

1. Login thanh cong va login that bai.
2. Chua login thi hien login screen.
3. Tao/chon conversation.
4. Gui message thanh cong.
5. AI timeout giu draft va retry duoc.
6. Logout xoa trang thai UI.
7. API client gui `credentials: "include"`.

## 6. Cac viec con lai cua Tú

- Them Vitest va React Testing Library.
- Viet cac automated test quan trong o muc tren.
- Khi Backend san sang, kiem tra refresh tai dung conversation/messages tu API.
- Kiem tra UI loading, unauthorized, API error, AI timeout va retry voi response that.
- Xac nhan logout goi Backend va session cu khong con dung duoc.
- Cap nhat README nay neu endpoint, port hoac schema thay doi.

## 7. Quy tac lam viec

- Khong tu y doi API schema trong Frontend; thay doi phai bao Minh va Hoan.
- Khong hard-code response AI trong happy path Backend.
- Khong goi `localhost:8001` tu Web.
- Khong dua secret, cookie, token hoac du lieu that vao repository.
- Truoc khi merge, chay diagnostics TypeScript, build va cac test da chon.
- Ghi lai file da sua, lenh da chay, ket qua va blocker con lai.

Tai lieu contract goc: `src/contracts-g1.md`.
Tai lieu phan cong: `src/01-phan-cong-giai-doan-1.md`.

from fastapi import FastAPI, Path

app = FastAPI()

@app.get("/user/{id}")
def read_item(id: int = Path(..., gt=0, lt=101)):
    return {"id": id, "title": f"这是第{id}本书"}

if __name__ == "__test__":
    import uvicorn
    uvicorn.run(app="__test__:app", host="127.0.0.1", port=8000, reload=True)

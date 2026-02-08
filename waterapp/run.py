# run.py
from waterapp import create_app

app = create_app()

if __name__ == "__main__":
    # Make sure ONLY this copy is running, or GPIO pins will be busy.
    app.run(host="0.0.0.0", port=8080,debug=False,use_reloader=False)

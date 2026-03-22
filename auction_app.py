from flask import Flask, render_template, request, redirect, url_for
import sqlite3 as sql

app = Flask(__name__)

host = 'http://127.0.0.1:5000/'

@app.route('/navigate', methods=['POST'])
def navigate():
    action = request.form.get('actions') # Get the selected value from the dropdown menu

    if action == 'add':
        return redirect(url_for('add_patient'))
    elif action == 'delete':
        return redirect(url_for('delete_patient'))
    return redirect(url_for('index'))


@app.route('/add', methods=['POST', 'GET']) # Add patient name page
def add_patient():
    error = None
    if request.method == 'POST':
        result = valid_name(request.form['FirstName'], request.form['LastName'])
        if result:
            return render_template('add_patient.html', error=error, result=result)
        else:
            error = 'invalid input name'
    result = get_all_patients()
    return render_template('add_patient.html', error=error, result=result)


def valid_name(first_name, last_name): # Helper function to input name and add it to the database
    connection = sql.connect('database.db')
    connection.execute('CREATE TABLE IF NOT EXISTS users(pid INTEGER PRIMARY KEY AUTOINCREMENT, firstname TEXT, lastname TEXT);') # modify to automatically generated pid
    connection.execute('INSERT INTO users (firstname, lastname) VALUES (?,?);', (first_name, last_name))
    connection.commit()
    cursor = connection.execute('SELECT * FROM users;')
    return cursor.fetchall()

if __name__ == "__main__":
    app.run()



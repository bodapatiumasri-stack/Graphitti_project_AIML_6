const API_URL = "https://platter-sandbox-derby.ngrok-free.dev";

const askButton = document.querySelector('.js-ask-button');

async function askQuestion() {

  const question = document.querySelector('.js-question-input').value;

  const answerText = document.querySelector('.answer-text');
  const statusText = document.querySelector('.status-text');

  if (question === '') {
    answerText.innerHTML = 'Please enter a medical question.';
    statusText.innerHTML =
      '<span class="status-dot">&bull;</span> Waiting for a question';
    return;
  }

  answerText.innerHTML = 'Searching the medical knowledge graph...';
  statusText.innerHTML =
    '<span class="status-dot">&bull;</span> Retrieving information...';

  askButton.disabled = true;

  try {

    const response = await fetch(`${API_URL}/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': '1'
      },
      body: JSON.stringify({
        question: question
      })
    });

    if (!response.ok) {
      throw new Error('Server Error');
    }

    const data = await response.json();

    answerText.innerHTML = data.answer;

    statusText.innerHTML =
      '<span class="status-dot">&bull;</span> Answer ready';

  } catch (error) {

    answerText.innerHTML =
      'Unable to connect to the medical knowledge graph.';

    statusText.innerHTML =
      '<span class="status-dot">&bull;</span> Connection failed';

    console.error(error);

  } finally {

    askButton.disabled = false;

  }

}

askButton.addEventListener('click', function () {
  askQuestion();
});

const questionInput = document.querySelector('.js-question-input');

questionInput.addEventListener('keydown', function (event) {
  if (event.key === 'Enter') {
    askQuestion();
  }
});

function resetResult() {
  document.querySelector('.answer-text').innerHTML = 'No answer yet.';
  document.querySelector('.status-text').innerHTML =
    '<span class="status-dot">&bull;</span> Knowledge base ready';
}

questionInput.addEventListener('input', resetResult);
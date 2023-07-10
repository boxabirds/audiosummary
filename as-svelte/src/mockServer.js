// mockServer.js

export async function processAudio(file) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          sentences: [
            { id: 1, text: "This is a short sentence.", selected: false },
            { id: 2, text: "This is slightly longer.", selected: false },
            { id: 3, text: "Here is the longest sentence of all, filled with grandeur and eloquence.", selected: false }
          ],
          audioPath: '/lesson-of-greatness-daniel-ek.mp3' // the path to your mp3 file
        });
      }, 2000); 
    });
  }
  
export async function processSelectedSentences(sentenceIds) {
    return new Promise((resolve) => {
      setTimeout(() => {
        console.log(`Sentences sent to the server: ${sentenceIds}`);
        resolve({
          audioPath: '/lesson-of-greatness-daniel-ek.mp3' // the path to your mp3 file
        });
      }, 2000);
    });
  }
  
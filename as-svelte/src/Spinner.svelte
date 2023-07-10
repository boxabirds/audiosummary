<!-- Spinner.svelte -->
<style>
    .spinner {
      position: fixed;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      width: 100vw;
      z-index: 9999;
      background-color: rgba(0, 0, 0, 0.7);
    }
  
    .loader {
      border: 16px solid #f3f3f3;
      border-radius: 50%;
      border-top: 16px solid blue;
      border-right: 16px solid green;
      border-bottom: 16px solid red;
      border-left: 16px solid pink;
      width: 120px;
      height: 120px;
      animation: spin 2s linear infinite;
    }
  
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  </style>
  
  <div class="spinner">
    <div class="loader"></div>
  </div>
  
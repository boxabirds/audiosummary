<script>
    import { createEventDispatcher } from 'svelte';
  
    const dispatch = createEventDispatcher();
    let file;
  
    // Declare the 'processing' prop
    export let processing;
  
    function handleFileChange(event) {
      file = event.target.files[0];
    }
  
    function handleUploadClick() {
      dispatch('upload', { file });
    }
  </script>
  
  <input type="file" accept=".mp3" on:change="{handleFileChange}" disabled="{processing}" />
  <button on:click="{handleUploadClick}" disabled="{processing || !file}">Upload</button>
  
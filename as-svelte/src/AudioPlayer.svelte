<script>
    import { createEventDispatcher } from 'svelte';
    import { Button } from 'svelte-materialify';
  
    export let finalAudio = '';
  
    const dispatch = createEventDispatcher();
  
    function handleNewSummaryClick() {
      dispatch('newSummary');
    }
</script>

<audio controls src="{finalAudio}"></audio>

<a href="{finalAudio}" download>
  <Button>Download</Button>
</a>

<Button on:click="{handleNewSummaryClick}">New Summary</Button>

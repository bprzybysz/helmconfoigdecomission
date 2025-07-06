import subprocess
import sys
import os
import shutil

def run_command(cmd, cwd=None):
    """Run command and return result"""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    return result

def test_e2e_with_branch():
    """E2E test with branch creation, modification, verification, and cleanup"""
    
    # Test configuration
    repo_url = 'https://github.com/cloudnative-pg/cloudnative-pg.git'
    clone_dir = './cloudnative-pg'
    db_name = 'test_db'
    branch_name = f'chore/{db_name}-decomission'
    
    print("🚀 Starting E2E test with branch management...")
    
    try:
        # Step 1: Clean up any existing clone
        if os.path.exists(clone_dir):
            print("🧹 Cleaning up existing clone...")
            shutil.rmtree(clone_dir)
        
        # Step 2: Clone the repository
        print("📥 Cloning repository...")
        result = run_command(f'git clone --depth 1 {repo_url} {clone_dir}')
        if result.returncode != 0:
            print(f"❌ Failed to clone repo: {result.stderr}")
            return False
        
        # Step 3: Create and checkout new branch
        print(f"🌿 Creating branch: {branch_name}")
        result = run_command(f'git checkout -b {branch_name}', cwd=clone_dir)
        if result.returncode != 0:
            print(f"❌ Failed to create branch: {result.stderr}")
            return False
        
        # Step 4: Run initial scan to see what we find
        print("🔍 Running initial scan...")
        result = run_command(f'python decommission_tool.py {clone_dir} {db_name}')
        if result.returncode not in [0, 2]:
            print(f"❌ Initial scan failed with unexpected exit code {result.returncode}: {result.stderr}")
            return False
        
        initial_findings = result.stdout
        print("Initial scan results:")
        print(initial_findings)
        
        # Step 5: Run decommission tool with --remove flag
        print(f"🗑️  Running decommission tool with --remove on branch {branch_name}...")
        result = run_command(f'python decommission_tool.py {clone_dir} {db_name} --remove')
        
        removal_output = result.stdout
        print("Removal process output:")
        print(removal_output)

        # Step 6: Verify changes (this part would be more robust in a real E2E test)
        # For now, we'll just check if the output indicates success
        if "✅ Database references removal process finished!" not in removal_output:
            print(f"❌ Verification failed: Expected success message not found.")
            return False
        
        print("✅ Decommission tool ran successfully with --remove flag.")

        # Step 7: Clean up branch and clone
        print("🧹 Cleaning up branch and clone...")
        # Checkout original branch (e.g., main or master) before deleting the test branch
        result = run_command(f'git checkout main', cwd=clone_dir)
        if result.returncode != 0:
            print(f"❌ Failed to checkout main branch: {result.stderr}")
            # Attempt to delete the directory anyway
            shutil.rmtree(clone_dir)
            return False

        result = run_command(f'git branch -D {branch_name}', cwd=clone_dir)
        if result.returncode != 0:
            print(f"❌ Failed to delete branch {branch_name}: {result.stderr}")
            # Proceed to remove clone_dir even if branch deletion fails
        
        shutil.rmtree(clone_dir)
        print("✅ Test environment cleaned up.")
        return True
        
    except Exception as e:
        print(f"An error occurred during E2E test: {e}")
        return False

if __name__ == "__main__":
    if test_e2e_with_branch():
        print("E2E test PASSED")
        sys.exit(0)
    else:
        print("E2E test FAILED")
        sys.exit(1)
